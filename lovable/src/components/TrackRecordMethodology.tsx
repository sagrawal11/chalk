const TrackRecordMethodology = ({ text }: { text: string }) => (
  <section className="rounded-xl border border-border/60 bg-card/40 p-6">
    <h2 className="text-lg font-semibold mb-2">How this works</h2>
    <p className="text-sm text-muted-foreground leading-relaxed">{text}</p>
    <ul className="mt-4 space-y-1 text-sm text-muted-foreground list-disc list-inside">
      <li>No betting lines are used as model inputs: the predictions are ours alone.</li>
      <li>Each pick is locked before tip-off and graded against the real final score.</li>
      <li>Winner accuracy counts every graded pick; ROI counts only picks settled at a real price.</li>
    </ul>
  </section>
);

export default TrackRecordMethodology;
