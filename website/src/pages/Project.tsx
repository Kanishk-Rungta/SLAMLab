import content from '../generated/content.json';
import { Icon, Link, PageHeader, REPO } from '../components/ui';
import { HtmlContent } from '../components/ContentTools';
import { ResearchResources } from '../components/ResearchResources';

const sections = [
  ['what-is-our-project-about', 'What is our project about?'],
  ['project-statement', 'Project statement'],
  ['problem-statement', 'Problem statement'],
  ['project-objectives', 'Project objectives'],
  ['methodology', 'Methodology'],
  ['project-guide', 'Project guide'],
  ['team-details', 'Team details'],
  ['project-progress', 'Project progress'],
  ['documentation', 'Documentation'],
  ['repository-link', 'Repository link'],
  ['demonstration-videos', 'Demonstration videos'],
];

export default function Project() {
  const document = content.documents.find((entry) => entry.id === 'project-overview')!;
  return (
    <>
      <PageHeader
        eyebrow="TEAM 98 · RESEARCH IN PROGRESS"
        title="Project overview"
        description="Edge-Based Multi-Robot System for Collaborative SLAM and Autonomous Task Coordination"
      />
      <section className="project-snapshot" aria-label="Current project status">
        <div className="panel">
          <span className="chip">Experimental</span>
          <h2>Mapping and exploration</h2>
          <p>
            The research foundation uses two robots in Webots. Mapping quality, localization
            reliability and extended operation need improvement.
          </p>
          <a className="text-link" href="https://github.com/Kanishk-Rungta/Final-Year-Project">
            Research source <Icon name="external" size={14} />
          </a>
        </div>
        <div className="panel">
          <span className="chip">Published teaching evidence</span>
          <h2>Landmark Lab recordings</h2>
          <p>
            One-robot and two-independent-robot examples have measured paths, maps and replay data.
            These do not establish collaborative SLAM.
          </p>
          <Link to="benchmarks/" className="text-link">
            Inspect recorded results <Icon name="arrow" size={14} />
          </Link>
        </div>
        <div className="panel">
          <span className="chip">Pending validation</span>
          <h2>Collaboration and hardware</h2>
          <p>
            Reliable shared mapping, autonomous task coordination and measured physical edge
            deployment remain development stages.
          </p>
          <a className="text-link" href="#project-progress">
            Progress and next stages <Icon name="arrow" size={14} />
          </a>
        </div>
      </section>
      <section className="panel research-workflow">
        <h2>How the pieces connect</h2>
        <p>
          Each robot needs a local understanding before the team can share maps and coordinate work.
          Dashed blocks mark planned integration.
        </p>
        <div className="flow-three">
          <div>
            <span className="eyebrow">LOCAL FOUNDATION</span>
            <strong>Observe → estimate position → build a map</strong>
          </div>
          <div className="planned">
            <span className="eyebrow">COLLABORATION · PLANNED</span>
            <strong>Exchange observations → connect local maps</strong>
          </div>
          <div className="planned">
            <span className="eyebrow">COORDINATION · PLANNED</span>
            <strong>Divide exploration work → evaluate on edge hardware</strong>
          </div>
        </div>
        <p className="help">
          Published teaching-run evidence was audited on 25 October 2026.{' '}
          <Link to="documentation/landmark-lab/">Read its sensor contract</Link> or{' '}
          <a href={REPO + '/blob/main/docs/activity-audit.md'}>inspect the verification record</a>.
        </p>
      </section>
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
        <article className="prose document project-document">
          <div className="doc-meta">
            <span className="eyebrow">TEAM 98 · RESEARCH IN PROGRESS</span>
            <a href={REPO}>
              GitHub <Icon name="external" size={13} />
            </a>
          </div>
          <HtmlContent html={document.html.slice(document.html.indexOf('<h2'))} />
          <Link to="studio/" className="next-lesson">
            <span>EXPLORE THE RECORDED DATA</span>
            <b>Open Landmark Lab in Studio →</b>
          </Link>
        </article>
      </div>
      <ResearchResources />
    </>
  );
}
