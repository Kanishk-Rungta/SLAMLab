import content from '../generated/content.json';
import { BASE, Icon, Link, REPO } from './ui';
import { CodeBlock, CopyButton } from './ContentTools';

export function ResearchResources({ sample = 'landmark-reference' }: { sample?: string }) {
  const manifest =
    content.manifests[sample as keyof typeof content.manifests] ||
    content.manifests['landmark-reference'];
  return (
    <section className="panel research-resources" aria-label="Citation and reproduction">
      <div>
        <p className="eyebrow">USE THE WORK</p>
        <h2>Cite, reproduce, and inspect.</h2>
        <p className="help">
          Software attribution follows the repository citation. Cite the original papers separately
          for the algorithms you use.
        </p>
        <blockquote>{content.citation}</blockquote>
        <CopyButton text={content.citation} label="Copy software citation" />
        <div className="resource-links">
          <a href={BASE + 'generated/CITATION.cff'} download>
            Download citation file
          </a>
          <Link to="documentation/references/">Original research references</Link>
        </div>
      </div>
      <div>
        <h3>
          Reproduce the {manifest.configuration.robots === 2 ? 'two-robot' : 'one-robot'} recording
        </h3>
        <p className="help">
          Requires Python and Webots R2025a locally. Use a fresh output directory.
        </p>
        <CodeBlock code={manifest.reproduce} label="Reproduce published recording" />
        <div className="resource-links">
          <a href={BASE + 'generated/' + sample + '-manifest.json'} download>
            Download run manifest
          </a>
          <a href={BASE + 'generated/landmark-slam.png'} download>
            <Icon name="download" size={14} />
            Landmark Lab overview figure (PNG)
          </a>
          <a href={REPO + '/tree/main/examples/results'}>Recorded data and provenance</a>
        </div>
        <p className="help">
          The overview figure is an existing measured Landmark Lab illustration. Each manifest
          identifies its own published replay, configuration and implementation hashes.
        </p>
      </div>
    </section>
  );
}
