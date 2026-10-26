import { StatusLine } from "./components/StatusLine";
import { fi } from "./i18n/fi";

export function App() {
  return (
    <>
      <header>
        <h1>{fi.app.title}</h1>
        {/* Feature specs add their pages here (first: Tuotteet). */}
        <nav aria-label={fi.app.navigation} />
        <StatusLine />
      </header>
      <main />
    </>
  );
}
