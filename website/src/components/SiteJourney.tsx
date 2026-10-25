import { Icon, Link } from './ui';
export function SiteJourney() {
  return (
    <nav className="site-journey" aria-label="Explore SLAMLab">
      {[
        ['learn/', 'Understand', 'See how a robot finds its place.', 'learn'],
        ['playground/', 'Experiment', 'Change one thing. See what happens.', 'lab'],
        ['simulations/', 'Run', 'Run a complete experiment locally.', 'simulation'],
        ['studio/', 'Inspect results', 'Replay the path and map it saved.', 'studio'],
      ].map(([to, title, description, icon], index) => (
        <Link key={to} to={to}>
          <span className="journey-index">
            0{index + 1}
            <Icon name={icon} size={19} />
          </span>
          <strong>{title}</strong>
          <span>{description}</span>
        </Link>
      ))}
    </nav>
  );
}
