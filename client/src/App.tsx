import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import DashboardLayout from "./components/DashboardLayout";
import AuditLog from "./pages/AuditLog";
import DisputeQueue from "./pages/DisputeQueue";
import EvidenceGenerator from "./pages/EvidenceGenerator";
import ImportData from "./pages/ImportData";
import Overview from "./pages/Overview";
import RiskFeed from "./pages/RiskFeed";
import Transparency from "./pages/Transparency";

function Router() {
  // make sure to consider if you need authentication for certain routes
  return (
    <DashboardLayout><Switch>
      <Route path={"/"} component={Overview} />
      <Route path={"/import"} component={ImportData} />
      <Route path={"/risk-feed"} component={RiskFeed} />
      <Route path={"/disputes"} component={DisputeQueue} />
      <Route path={"/evidence"} component={EvidenceGenerator} />
      <Route path={"/transparency"} component={Transparency} />
      <Route path={"/audit-log"} component={AuditLog} />
      <Route path={"/404"} component={NotFound} />
      <Route component={NotFound} />
    </Switch></DashboardLayout>
  );
}

// NOTE: About Theme
// - First choose a default theme according to your design style (dark or light bg), than change color palette in index.css
//   to keep consistent foreground/background color across components
// - If you want to make theme switchable, pass `switchable` ThemeProvider and use `useTheme` hook

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider
        defaultTheme="light"
        // switchable
      >
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
