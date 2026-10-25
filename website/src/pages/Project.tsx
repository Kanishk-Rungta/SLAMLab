import content from '../generated/content.json';
import { Icon, Link, REPO } from '../components/ui';

const sections = [
  ['project-statement', 'Project statement'],
  ['problem-statement', 'Problem statement'],
  ['project-objectives', 'Project objectives'],
  ['methodology', 'Methodology'],
  ['team-details', 'Team details'],
  ['project-progress', 'Project progress'],
  ['documentation', 'Documentation'],
  ['repository-link', 'Repository link'],
  ['demonstration-videos', 'Demonstration videos'],
];

export default function Project() {
  const document = content.documents.find((entry) => entry.id === 'project-overview')!;
  return (
    <div className="doc-layout">
      <nav className="doc-nav" aria-label="Project sections">
        <Link to="about/" className="text-link">
          About SLAMLab <Icon name="arrow" size={13} />
        </Link>
        {sections.map(([id, title]) => (
          <a href={'#' + id} key={id}>
            {title}
          </a>
        ))}
      </nav>
      <article className="prose document">
        <div className="doc-meta">
          <span className="eyebrow">TEAM 98 · RESEARCH IN PROGRESS</span>
          <a href={REPO}>
            GitHub <Icon name="external" size={13} />
          </a>
        </div>
        <div dangerouslySetInnerHTML={{ __html: document.html }} />
        <Link to="studio/" className="next-lesson">
          <span>EXPLORE THE RECORDED DATA</span>
          <b>Open Landmark Lab in Studio →</b>
        </Link>
      </article>
    </div>
  );
}
