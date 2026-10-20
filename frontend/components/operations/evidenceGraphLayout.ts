import { type Case, channelName } from "@/lib/operations";

export type GraphNode = { id: string; kind: string };
export type GraphEdge = { from: string; to: string; label: string };

const MAX_CASES = 8;
const MAX_NODES = 16;
const COLUMN_X = { case: 92, account: 253, reference: 428 };

/** Beneficiaries and instruments share the "connected references" column. */
export const nodeGroup = (kind: string) => (kind === "case" || kind === "account" ? kind : "reference");

/** Nodes, edges and positions for up to eight cases: investigations, accounts, then connected references. */
export function buildEvidenceGraph(cases: Case[]) {
  const nodes = new Map<string, GraphNode>();
  const edges: GraphEdge[] = [];
  cases.slice(0, MAX_CASES).forEach((item) => {
    nodes.set(item.account_id, { id: item.account_id, kind: "account" });
    nodes.set(item.case_id, { id: item.case_id, kind: "case" });
    edges.push({
      from: item.account_id,
      to: item.case_id,
      label: channelName(item.channel),
    });
    item.related_accounts.slice(0, 4).forEach((account) => {
      nodes.set(account, { id: account, kind: "account" });
      edges.push({ from: item.account_id, to: account, label: "shared-device evidence" });
    });
    item.related_transactions.slice(0, 8).forEach((txn) => {
      nodes.set(txn.account_id, { id: txn.account_id, kind: "account" });
      const target = txn.beneficiary_id || txn.instrument_id;
      if (target) {
        nodes.set(target, {
          id: target,
          kind: txn.beneficiary_id ? "beneficiary" : "instrument",
        });
        if (!edges.some((x) => x.from === txn.account_id && x.to === target))
          edges.push({
            from: txn.account_id,
            to: target,
            label: txn.beneficiary_id ? "beneficiary" : "instrument",
          });
      }
    });
  });
  const list = [...nodes.values()].slice(0, MAX_NODES);
  const maxRows = Math.max(
    1,
    ...["case", "account", "reference"].map(
      (kind) => list.filter((node) => nodeGroup(node.kind) === kind).length,
    ),
  );
  const graphHeight = Math.max(380, 110 + maxRows * 65);
  const positions = new Map(
    list.map((node, i) => {
      const peers = list.filter((x) => nodeGroup(x.kind) === nodeGroup(node.kind));
      const index = peers.findIndex((x) => x.id === node.id);
      const column = COLUMN_X[nodeGroup(node.kind) as keyof typeof COLUMN_X];
      return [
        node.id,
        { x: column + (i % 2 ? 8 : -8), y: 55 + (index + 0.5) * ((graphHeight - 110) / peers.length) },
      ];
    }),
  );
  return { list, edges, positions, graphHeight, nodeCount: nodes.size };
}
