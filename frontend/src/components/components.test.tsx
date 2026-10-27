import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { sampleReport } from "@/test/helpers";
import { initialRunState } from "@/lib/state";
import { ApiError } from "@/lib/stream";
import { AgentNetwork } from "./AgentNetwork";
import { Console, CUSTOM } from "./Console";
import { ErrorPanel } from "./ErrorPanel";
import { Footer } from "./Footer";
import { ReportView } from "./ReportView";

const scenarios = [
  { id: "hiring", title: "Recruitment screening", category: "Employment", description: "x".repeat(40) },
];

function renderConsole(description: string, onRun = vi.fn()) {
  render(
    <Console
      scenarios={scenarios}
      scenariosError={false}
      onRetryScenarios={() => undefined}
      selectedId={CUSTOM}
      onSelect={() => undefined}
      description={description}
      onDescription={() => undefined}
      running={false}
      onRun={onRun}
      onCancel={() => undefined}
      edited={false}
    />,
  );
  return onRun;
}

describe("Console", () => {
  it("shows the character count and blocks a run that is too short", async () => {
    const onRun = renderConsole("too short");
    expect(screen.getByText(/9 \/ 6000/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run assessment/i })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: /run assessment/i }));
    expect(onRun).not.toHaveBeenCalled();
  });
  it("runs when the description is valid", async () => {
    const onRun = renderConsole("A hiring tool that ranks candidates from their CVs.");
    await userEvent.click(screen.getByRole("button", { name: /run assessment/i }));
    expect(onRun).toHaveBeenCalledTimes(1);
  });
  it("offers the scenarios and a custom option", () => {
    renderConsole("");
    expect(screen.getAllByRole("radio")).toHaveLength(2);
  });
});

describe("ErrorPanel", () => {
  it("announces the error and offers a retry for retryable kinds", async () => {
    const retry = vi.fn();
    render(<ErrorPanel error={new ApiError("report_lost", "Run again.")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("The report did not arrive");
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(retry).toHaveBeenCalled();
  });
  it("does not offer a retry for validation errors", () => {
    render(<ErrorPanel error={new ApiError("validation", "Too short.")} onRetry={() => undefined} />);
    expect(screen.queryByRole("button", { name: /try again/i })).toBeNull();
  });
});

describe("ReportView", () => {
  it("renders the key sections and the disclaimer", () => {
    render(<ReportView report={sampleReport} />);
    expect(screen.getByRole("heading", { name: /assessment report/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /executive summary/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /agent consensus/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /limitations/i })).toBeInTheDocument();
    expect(screen.getByText(/does not constitute legal advice/i)).toBeInTheDocument();
  });
});

describe("AgentNetwork and Footer", () => {
  it("lists the seven agents", () => {
    render(<AgentNetwork run={initialRunState()} />);
    for (const name of [/orchestrator/i, /^risk$/i, /data governance/i, /^security$/i, /human oversight/i, /^governance$/i, /critic/i]) {
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    }
  });
  it("credits the author", () => {
    render(<Footer />);
    expect(screen.getByText(/portfolio project by shahil/i)).toBeInTheDocument();
  });
  it("links to the source repository safely", () => {
    render(<Footer />);
    const link = screen.getByRole("link", { name: "View source on GitHub" });
    expect(link).toHaveAttribute("href", "https://github.com/shahil5z/europa-ai-governance");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
