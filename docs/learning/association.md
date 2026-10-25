# Feature detection and data association

A detector proposes repeatable image locations. A descriptor summarizes nearby
appearance. Association decides which observations refer to the same structure.
A good detector does not make every descriptor match correct.

## Appearance and geometry

For descriptor vectors $a,b$, Euclidean distance is
$d(a,b)=\sqrt{\sum_i(a_i-b_i)^2}$. A threshold rejects distant pairs. Mutual
nearest-neighbor checking requires each descriptor to select the other. Repeated
texture can still produce confident wrong matches.

**Feature matching** generates synthetic feature sets with missing observations
and outliers. Matching uses descriptors, not the hidden identities used to color
correct/incorrect results. Adjust noise, threshold and mutual checking. Observe
both rejected true matches and accepted outliers rather than equating more
matches with better tracking.

Real pipelines further check epipolar geometry, reprojection residuals, robust
models and motion consistency. A loop candidate should not become a graph edge
solely because its appearance score is high.

The reference EKF assumes known marker identities. Its innovation gate tests
consistency with the current belief; it does not solve general image matching.
Compare that contract with [visual SLAM](visual.md) and the
[research systems](../../algorithms/README.md).

## Visual exercise

In the Feature matching playground, use **Try a clean match**, then select **A2**,
the upper-right corner of the left window. Inspect its nearest candidate in view B,
the descriptor distance and the acceptance decision.

Next select **A1**. Its corresponding corner was not detected in the second view,
so a similar description does not necessarily identify the same physical detail.
Use **Try confusing details**, compare the three nearest descriptors, then tighten
the threshold or enable mutual nearest neighbors. Watch how the acceptance reason
and correct/wrong counts change.

The numbered room views are schematic, with provided corners and generated
descriptors. The teaching check reveals known identities after matching; those
identities are not inputs to the matching decision.
