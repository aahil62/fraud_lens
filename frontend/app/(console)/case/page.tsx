import CaseWorkspace from "@/components/operations/CaseWorkspace";
export default async function Page({ searchParams }: { searchParams: Promise<{ case_id?: string }> }) {
  const params = await searchParams;
  return <CaseWorkspace caseId={params.case_id ?? ""} />;
}
