# Inside landmark EKF-SLAM

One joint Gaussian covers robot and landmarks:
$\mu=[x,y,\theta,m_{1x},m_{1y},\ldots]^T$. Off-diagonal covariance blocks encode
correlation: landmarks seen from the same uncertain pose have related errors.

## Predict and initialize

Wheel motion propagates the full covariance. For a new marker at range $r$ and
bearing $\beta$,

$$
m_x=x+r\cos(\theta+\beta),\qquad m_y=y+r\sin(\theta+\beta).
$$

State and observation Jacobians initialize the landmark's covariance and its
cross-covariance. Appending an independent point would discard information needed
for later joint correction.

## Reobserve and correct

For predicted measurement $h(\mu^-)$ and Jacobian $H$,

$$
S=HP^-H^T+R,\quad K=P^-H^TS^{-1},\quad \mu^+=\mu^-+K(z-h(\mu^-)).
$$

Wrap the bearing residual. The Mahalanobis innovation gate rejects inconsistent
observations. A Joseph covariance update improves numerical stability.
Reobservations correct both pose and map through their correlation. No global
landmark coordinates enter the estimator; the configured initial pose fixes the
gauge.

Read the [implementation](../../algorithms/ekf-slam/ekf.py),
[tests](../../tests/test_ekf_slam.py) and [Webots guide](../../examples/landmark-slam/README.md).
Static identified landmarks and local Gaussian linearization define its scope.
