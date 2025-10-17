import Hero from "../sections/Hero";
import Tagline from "../sections/Tagline";
import ProblemsSection from "../sections/ProblemsSection";
import SolutionSection from "../sections/SolutionSection";
import UseCasesSection from "../sections/UseCasesSection";

export default function Home() {
  return (
    <>
      <Hero />
      <Tagline />
      <ProblemsSection />
      <SolutionSection />
      <UseCasesSection />
    </>
  );
}
