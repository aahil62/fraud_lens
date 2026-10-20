import Link from "next/link";
import { LensMark } from "./console/LensMark";

function AuthOptic() {
  return (
    <div className="auth-optic" aria-hidden="true">
      <svg viewBox="0 0 450 210" fill="none">
        <path
          className="optic-path"
          d="M0 45h140c55 0 50 60 100 60h210M0 105h450M0 165h140c55 0 50-60 100-60h210"
          strokeWidth="1.3"
        />
        <ellipse
          className="optic-ring"
          cx="240"
          cy="105"
          rx="59"
          ry="90"
          strokeWidth="2"
          transform="rotate(-24 240 105)"
        />
        <ellipse
          className="optic-rim"
          cx="262"
          cy="105"
          rx="59"
          ry="90"
          strokeWidth="6"
          transform="rotate(-24 262 105)"
        />
        <ellipse
          className="optic-glint"
          cx="251"
          cy="105"
          rx="59"
          ry="90"
          strokeWidth="1"
          transform="rotate(-24 251 105)"
        />
        <circle className="optic-dot" cx="82" cy="45" r="5" />
        <circle className="optic-dot" cx="123" cy="165" r="5" />
        <circle className="optic-signal" cx="371" cy="105" r="6" />
      </svg>
    </div>
  );
}

export default function AuthFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className="auth-page">
      <section className="auth-story" aria-label="About the workspace">
        <Link href="/" className="ops-brand">
          <LensMark />
          FraudLens
        </Link>
        <div className="auth-story-content">
          <h2>
            A clearer picture.
            <br />A considered decision.
          </h2>
          <p>
            Follow a payment from its first signal to a documented outcome. Your evidence, actions and team,
            in one workspace.
          </p>
          <AuthOptic />
        </div>
        <p className="auth-story-bottom">
          A local simulation of UPI, net banking, card and ATM investigation. Built for learning, with test
          accounts only.
        </p>
      </section>
      <section className="auth-form-side">{children}</section>
    </main>
  );
}
