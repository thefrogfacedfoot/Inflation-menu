export default function AccountHealthGuidePage() {
  return (
    <div>
      <h1>About account health</h1>
      <section style={section}>
        <h2>Shadowban detection</h2>
        <p>
          Reddit can silently filter your posts so other users don&apos;t see them
          but you do. We periodically fetch your profile two ways — with your
          account&apos;s token (what <em>you</em> see) and with no token (what
          <em>everyone else</em> sees) — and compare. A material, sustained gap
          is the signal.
        </p>
      </section>
      <section style={section}>
        <h2>Karma trend</h2>
        <p>
          We snapshot your karma every day. If your last 7 days drop by 50 or
          more, or by 30%+ relative to the baseline, we warn you. If that drop
          sustains over 14 days, we alert.
        </p>
      </section>
      <section style={section}>
        <h2>Slow-burn removals</h2>
        <p>
          The auto-pause check looks at your last 10 posts. A drip of one
          removal every few days never trips that window, but is still
          consequential. We look at the last 30 with the std-dev of removal
          times to tell &ldquo;burst&rdquo; (already handled) from
          &ldquo;slow drip&rdquo; (this check).
        </p>
      </section>
    </div>
  );
}

const section: React.CSSProperties = {
  background: "#16161a",
  padding: 16,
  borderRadius: 8,
  margin: "16px 0",
};
