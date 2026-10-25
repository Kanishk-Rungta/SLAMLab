import { Fragment, lazy, Suspense, useEffect, useState } from 'react';
import content from './generated/content.json';
import { lessonOrder } from './lab/learning';
import { BASE, Icon, Link, Navigation, REPO } from './components/ui';
import Project from './pages/Project';
import {
  About,
  Algorithms,
  Benchmarks,
  Documentation,
  Home,
  Learn,
  Simulations,
} from './pages/Pages';
const Playground = lazy(() => import('./pages/Playground'));
const Studio = lazy(() => import('./pages/Studio'));

const nav = [
  ['', 'Home', 'home'],
  ['learn/', 'Learn', 'learn'],
  ['playground/', 'Playground', 'lab'],
  ['algorithms/', 'Algorithms', 'algorithms'],
  ['simulations/', 'Simulation Lab', 'simulation'],
  ['studio/', 'Studio', 'studio'],
  ['benchmarks/', 'Benchmarks', 'chart'],
  ['documentation/', 'Documentation', 'docs'],
  ['project/', 'Project', 'simulation'],
  ['about/', 'About', 'about'],
];
export default function App() {
  const [url, setUrl] = useState(location.pathname + location.search),
    [menu, setMenu] = useState(false);
  const [dark, setDark] = useState(document.documentElement.dataset.theme === 'dark');
  const path = url
    .split('?')[0]
    .replace(BASE, '')
    .replace(/^\/+|\/+$/g, '');
  const navPath =
    path.startsWith('documentation/') && lessonOrder.includes(path.split('/')[1]) ? 'learn' : path;
  function navigate(to: string) {
    history.pushState({}, '', BASE + to.replace(/^\//, ''));
    setUrl(location.pathname + location.search);
    setMenu(false);
    window.scrollTo(0, 0);
  }
  useEffect(() => {
    const pop = () => setUrl(location.pathname + location.search);
    addEventListener('popstate', pop);
    return () => removeEventListener('popstate', pop);
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    try {
      localStorage.setItem('slamlab-theme', dark ? 'dark' : 'light');
    } catch {
      /* Theme still works without persistent storage. */
    }
  }, [dark]);
  useEffect(() => {
    const doc = content.documents.find((d) => path === 'documentation/' + d.id);
    const algorithm = content.catalog.find((a) => path === 'algorithms/' + a.id);
    document.title =
      (doc?.title ||
        algorithm?.name ||
        nav.find((n) => n[0].replace(/\/$/, '') === path)?.[1] ||
        'Explore') + ' · SLAMLab';
    document.getElementById('main')?.focus({ preventScroll: true });
  }, [path]);
  let page;
  if (!path) page = <Home />;
  else if (path === 'learn') page = <Learn />;
  else if (path === 'playground') page = <Playground />;
  else if (path === 'studio') page = <Studio key={url} />;
  else if (path.startsWith('algorithms')) page = <Algorithms id={path.split('/')[1]} />;
  else if (path === 'simulations') page = <Simulations />;
  else if (path === 'benchmarks') page = <Benchmarks />;
  else if (path === 'project') page = <Project />;
  else if (path.startsWith('documentation')) page = <Documentation id={path.split('/')[1]} />;
  else if (path === 'about') page = <About />;
  else
    page = (
      <section className="empty">
        <h1>That route is off the map.</h1>
        <Link to="" className="button">
          Return home
        </Link>
      </section>
    );
  return (
    <Navigation value={navigate}>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="topbar">
        <Link to="" className="brand">
          <img src={BASE + 'generated/logo.svg'} width="34" height="34" alt="" />
          <strong>
            SLAM<span>Lab</span>
          </strong>
          <small>OPEN ROBOTICS</small>
        </Link>
        <div className="top-actions">
          <a href={REPO} className="github-link">
            GitHub <Icon name="external" size={14} />
          </a>
          <button
            className="icon-button"
            aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'}
            onClick={() => setDark(!dark)}
          >
            <Icon name={dark ? 'sun' : 'moon'} />
          </button>
          <button
            className="icon-button mobile-menu"
            aria-label="Toggle navigation"
            aria-expanded={menu}
            onClick={() => setMenu(!menu)}
          >
            <Icon name={menu ? 'close' : 'menu'} />
          </button>
        </div>
      </header>
      <aside className={'sidebar ' + (menu ? 'open' : '')}>
        <p className="nav-caption">EXPLORE THE LAB</p>
        <nav aria-label="Main navigation">
          {nav.map(([to, title, icon], index) => (
            <Fragment key={to}>
              {[0, 3, 7].includes(index) && (
                <p className="nav-group-label">
                  {index === 0
                    ? 'UNDERSTAND & TRY'
                    : index === 3
                      ? 'RUN & INSPECT'
                      : 'PROJECT & GUIDES'}
                </p>
              )}
              <Link
                key={to}
                to={to}
                className={
                  'nav-item ' +
                  ((to ? navPath.startsWith(to.replace(/\/$/, '')) : !navPath) ? 'active' : '')
                }
              >
                <Icon name={icon} size={19} />
                {title}
                {title === 'Playground' && <span className="nav-pill">5</span>}
              </Link>
            </Fragment>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> Open source. Open exploration.
          <a href={REPO + '/issues'}>
            Build with us <Icon name="arrow" size={15} />
          </a>
        </div>
      </aside>
      <div className="workspace">
        <main id="main" tabIndex={-1} key={path}>
          <Suspense fallback={<p role="status">Opening the lab...</p>}>{page}</Suspense>
        </main>
        <footer>
          <span>SLAMLab · From motion to understanding.</span>
          <div>
            <a href={REPO + '/blob/main/LICENSE'}>MIT & upstream licenses</a>
            <a href={REPO + '/blob/main/CITATION.cff'}>Cite SLAMLab</a>
            <a href={REPO}>
              Source <Icon name="external" size={12} />
            </a>
          </div>
        </footer>
      </div>
    </Navigation>
  );
}
