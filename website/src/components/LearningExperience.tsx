import { useContext, useEffect, useState } from 'react';
import { lessonConcepts, lessonOrder } from '../lab/learning';
import { Icon, Link, Navigation, REPO } from './ui';
import { LessonVisual } from './LessonVisual';

type LessonDocument = { id: string; title: string; html: string; source: string };

export function LearningExperience({ doc }: { doc: LessonDocument }) {
  const navigate = useContext(Navigation);
  const [step, setStep] = useState(0),
    [notesOpen, setNotesOpen] = useState(false),
    [anchor, setAnchor] = useState<string | null>(null);
  const concept = lessonConcepts[doc.id],
    index = lessonOrder.indexOf(doc.id);
  const previous = lessonOrder[index - 1],
    next = lessonOrder[index + 1];
  const headingEnd = doc.html.includes('</h1>') ? doc.html.indexOf('</h1>') + 5 : 0;
  const headingId = doc.html.match(/<h1 id="([^"]+)"/)?.[1];
  useEffect(() => {
    const revealNotes = () => {
      if (!location.hash) return;
      let target: string;
      try {
        target = decodeURIComponent(location.hash.slice(1));
      } catch {
        return;
      }
      if (!doc.html.includes(`id="${target}"`)) return;
      setAnchor(target);
      if (target !== headingId) setNotesOpen(true);
    };
    revealNotes();
    addEventListener('hashchange', revealNotes);
    return () => removeEventListener('hashchange', revealNotes);
  }, [doc.id, doc.html, headingId]);
  useEffect(() => {
    if (!anchor || (anchor !== headingId && !notesOpen)) return;
    let cancelled = false;
    const scroll = () => {
      if (!cancelled) document.getElementById(anchor)?.scrollIntoView({ block: 'start' });
    };
    // Wait for the disclosure to render before resolving an existing lesson link.
    const frame = requestAnimationFrame(scroll);
    void document.fonts.ready.then(scroll);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [anchor, notesOpen, headingId]);
  return (
    <article className="learning-experience">
      <div className="course-navigation">
        <Link to="learn/" className="text-link">
          ← All questions
        </Link>
        <span>LESSON {String(index + 1).padStart(2, '0')} / 12</span>
        <label className="course-jump">
          <span className="sr-only">Choose a lesson</span>
          <select
            value={doc.id}
            onChange={(event) => navigate('documentation/' + event.target.value + '/')}
          >
            {lessonOrder.map((id, position) => (
              <option key={id} value={id}>
                {position + 1}. {lessonConcepts[id].question}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="slam-context">
        <span className="context-mark" aria-hidden="true">
          <Icon name="simulation" size={20} />
        </span>
        <p>
          <strong>The mission:</strong> explore an unfamiliar room. <strong>SLAM:</strong> find your
          position while building its map.
        </p>
      </div>
      <header className="learning-masthead">
        <p className="eyebrow">{doc.title}</p>
        <h1 id={headingId}>{concept.question}</h1>
        <p>{concept.context}</p>
      </header>
      <LessonVisual id={doc.id} currentStep={step} onStepChange={setStep} />
      {step === 2 && (
        <section className="learning-handoff" aria-label="Connect to the next lesson">
          <div>
            <span className="eyebrow">TAKE THIS WITH YOU</span>
            <h2>{concept.takeaway}</h2>
            <p>{concept.bridge}</p>
          </div>
          <Link to={next ? 'documentation/' + next + '/' : 'simulations/'} className="button">
            {next ? 'Next: ' + lessonConcepts[next].question : 'Run a simulation'}
            <Icon name="arrow" size={16} />
          </Link>
        </section>
      )}
      <div className="lesson-extras">
        <details className="learning-terms">
          <summary>Two useful terms</summary>
          <dl>
            {concept.terms.map(([term, definition]) => (
              <div key={term}>
                <dt>{term}</dt>
                <dd>{definition}</dd>
              </div>
            ))}
          </dl>
        </details>
        <details
          className="learning-notes"
          open={notesOpen}
          onToggle={(event) => setNotesOpen(event.currentTarget.open)}
        >
          <summary>Equations & detailed notes</summary>
          <div className="prose">
            <div dangerouslySetInnerHTML={{ __html: doc.html.slice(headingEnd) }} />
            <a className="text-link" href={REPO + '/blob/main/' + doc.source}>
              View the shared source <Icon name="external" size={13} />
            </a>
          </div>
        </details>
      </div>
      <nav className="chapter-navigation" aria-label="Lesson navigation">
        {previous ? (
          <Link to={'documentation/' + previous + '/'}>← {lessonConcepts[previous].question}</Link>
        ) : (
          <Link to="learn/">← Learning overview</Link>
        )}
        {next && <Link to={'documentation/' + next + '/'}>{lessonConcepts[next].question} →</Link>}
      </nav>
    </article>
  );
}
