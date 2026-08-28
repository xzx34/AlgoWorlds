export interface SiteCopy {
  metaDescription: string;
  skip: string;
  nav: {
    abstract: string;
    benchmark: string;
    results: string;
    label: string;
    home: string;
  };
  masthead: {
    title: string;
    actionsLabel: string;
  };
  abstract: {
    heading: string;
    paragraph: string;
  };
  paperFigure: {
    alt: string;
    caption: string;
    fullSize: string;
    scrollHint: string;
  };
  benchmark: {
    heading: string;
    paragraphs: string[];
    statsHeading: string;
    facts: Array<{ value: string; label: string }>;
    validationHeading: string;
    validationIntro: string;
    validationFacts: Array<{ value: string; label: string }>;
    flowHeading: string;
    flowIntro: string;
    flowStages: Array<{ title: string; body: string }>;
    familiesHeading: string;
    familiesIntro: string;
    task: string;
    decision: string;
    instanceData: string;
    method: string;
    tools: string;
    competenciesHeading: string;
    competenciesLead: string;
    competencies: Array<{ title: string; body: string }>;
    evaluationHeading: string;
    evaluationBody: string;
    layer: string;
    measures: string;
    diagnosticQuestion: string;
    metricLayers: Array<{ layer: string; measures: string; question: string }>;
  };
  results: {
    heading: string;
    paragraphs: string[];
    diagnosticHeading: string;
    diagnosticText: string;
    exact: string;
    optimalOutcome: string;
    feasibleSuboptimal: string;
    infeasible: string;
    noDecisionOrProtocol: string;
    leaderboardHeading: string;
    leaderboardIntro: string;
    finalDecisionGroup: string;
    trajectoryGroup: string;
    model: string;
    feasible: string;
    utility: string;
    sufficiency: string;
    discovery: string;
    errorNote: string;
  };
  footer: {
    summary: string;
    detail: string;
  };
}

export const copy: SiteCopy = {
  metaDescription:
    "AlgoWorlds evaluates whether LLM agents can turn information acquired through tools into globally optimal decisions.",
  skip: "Skip to content",
  nav: {
    abstract: "Abstract",
    benchmark: "Benchmark",
    results: "Results",
    label: "Project navigation",
    home: "Weixin AI · AlgoWorlds home",
  },
  masthead: {
    title: "AlgoWorlds: Benchmarking Tool Use for Global Optimization in Algorithmic Worlds",
    actionsLabel: "Project resources",
  },
  abstract: {
    heading: "Abstract",
    paragraph:
      "Tool-use benchmarks generally evaluate whether an agent completes a workflow using appropriate tools and valid arguments. However, feasibility alone is insufficient in decision settings such as route planning and fleet dispatch: individual choices interact through shared constraints and costs, so a feasible solution may still be substantially suboptimal. AlgoWorlds evaluates whether LLM agents can turn information acquired through tools into globally optimal decisions. It transforms formally specified combinatorial optimization problems into partially observed decision environments with verifiable global optima. Each environment contains a hidden optimization instance that the agent observes only through sequential calls to task-specific information tools. The agent may then commit at most one structured decision, which an independent family-specific checker evaluates for feasibility and objective value; exact optimality is determined against a separately verified optimum. Family-specific deterministic programs generate 120 hidden instances, while exact algorithms certify their global optima and determine their workload levels. Each instance is exposed through paired Direct and Mediated interfaces that preserve the same decision problem under different information presentations, yielding 240 algorithmic worlds across ten optimization families and four workload levels. Independent offline checks confirm the optima and paired-interface equivalence. Across seven leading LLMs, the best-performing model reaches exact optimality in only 38.61% of cases. Even when recorded trajectories contain sufficient information to reconstruct the hidden instance, most failures end in feasible but suboptimal decisions. The challenge therefore extends beyond information acquisition to information integration, global constraint reasoning, and decision verification.",
  },
  paperFigure: {
    alt: "Exact-optimality rates for seven evaluated LLMs; GPT-5.6 Sol evaluations divided by information sufficiency, with the sufficient subset broken down by final-decision outcome; and a Transit Routing case where a feasible 24-leg route has 9.6% lower travel time but 241.5% higher transfer cost than the certified optimum, producing an objective 63.3% higher.",
    caption: "Sufficient information does not guarantee global optimality.",
    fullSize: "View full-size figure",
    scrollHint: "Scroll horizontally to inspect the figure.",
  },
  benchmark: {
    heading: "Benchmark Details",
    paragraphs: [
      "An algorithmic world combines a textual decision problem, a hidden optimization instance, and a suite of task-specific tools with per-call costs and a total access budget. The agent receives the question, tool schemas, per-call costs, and access budget—but not the hidden instance—and may submit at most one terminal structured decision.",
      "AlgoWorlds contains 120 hidden instances across ten formally specified combinatorial optimization families and four algorithm-grounded workload levels. Each instance is presented through paired Direct and Mediated interfaces that preserve the question, tool-call costs, access budget, and final-decision format while changing the relational organization of the returned information.",
    ],
    statsHeading: "Benchmark Structure",
    facts: [
      { value: "120", label: "Hidden instances" },
      { value: "240", label: "Algorithmic worlds" },
      { value: "10", label: "Optimization families" },
      { value: "4", label: "Algorithm-grounded workload levels" },
      { value: "2", label: "Paired interfaces per instance" },
      { value: "≤1", label: "Terminal structured decision" },
    ],
    validationHeading: "Data Quality",
    validationIntro: "Before model evaluation, every world is checked for scoring validity, in-budget information access, and paired-interface equivalence.",
    validationFacts: [
      { value: "120", label: "hidden instances with independently confirmed unique optima" },
      { value: "240", label: "algorithmic worlds passing scoring checks" },
      { value: "480", label: "validated in-budget acquisition plans" },
      { value: "648", label: "channel-level counterfactual checks" },
      { value: "1,464", label: "response-level counterfactual checks" },
      { value: "120", label: "equivalent Direct–Mediated pairs" },
    ],
    flowHeading: "Benchmark Construction",
    flowIntro: "For each optimization family, construction proceeds in three stages.",
    flowStages: [
      {
        title: "Deterministic instance generation",
        body: "A human-written deterministic generator produces each hidden instance from explicit size and structural parameters.",
      },
      {
        title: "Exact solution and workload calibration",
        body: "A family-specific exact algorithm solves each instance and records the executed work used to assign one of four shared workload levels.",
      },
      {
        title: "Tool-mediated world construction",
        body: "The same hidden instance is exposed through paired Direct and Mediated interfaces with fixed call costs and an access budget.",
      },
    ],
    familiesHeading: "Optimization Families",
    familiesIntro:
      "Each family defines its decision space, hidden instance data, exact solution method, and suite of information tools. Tool counts exclude the final-decision tool.",
    task: "Task family",
    decision: "Decision",
    instanceData: "Instance data",
    method: "Exact solution method",
    tools: "Information tools",
    competenciesHeading: "What Each World Requires",
    competenciesLead:
      "These capabilities are jointly required; AlgoWorlds evaluates the resulting trajectory and decision without attributing an individual failure to any single stage.",
    competencies: [
      { title: "Information acquisition", body: "Select sequential information calls under positive per-call costs and a fixed access budget." },
      { title: "Cross-tool integration", body: "Join entities, relations, constraints, and objective terms distributed across returned records." },
      { title: "Coupled optimization", body: "Compare complete decisions whose components interact through shared constraints and aggregate costs." },
      { title: "Final verification", body: "Check feasibility and objective value before committing a terminal structured decision, which can be submitted at most once." },
    ],
    evaluationHeading: "Evaluation Metrics",
    evaluationBody:
      "Three final-decision metrics score the submitted decision, while two trajectory diagnostics characterize the decision information recoverable from fact-revealing tool responses. The diagnostics do not establish that the agent recognized, reconstructed, or correctly used that information.",
    layer: "Aspect",
    measures: "Metric",
    diagnosticQuestion: "Definition",
    metricLayers: [
      { layer: "Final decision", measures: "Exact optimality", question: "Binary; the decision is feasible and attains the verified global optimum. This is the primary metric." },
      { layer: "Final decision", measures: "Feasibility", question: "Binary; the family-specific checker accepts the submitted structured decision as feasible." },
      { layer: "Final decision", measures: "Reference utility", question: "A feasible decision receives U in [0,1]; results report 100 × U, so the global optimum is 100 and the fixed suboptimal reference decision is 0." },
      { layer: "Trajectory", measures: "Information sufficiency", question: "Binary; joint normalization of the fact-revealing tool responses recovers at least one verified sufficient fact set in full." },
      { layer: "Trajectory", measures: "Discovery coverage", question: "The largest fraction, in [0,1], of any verified sufficient fact set recovered through joint normalization of the fact-revealing tool responses." },
    ],
  },
  results: {
    heading: "Results",
    paragraphs: [
      "Exact optimality, the primary metric, remains low for every evaluated model: mean rates range from 5.42% for Qwen 3.5 Plus to 38.61% for Claude Opus 4.8, with GPT-5.6 Sol close behind at 38.19%. By contrast, Opus and Sol produce feasible decisions in 96.25% and 97.50% of evaluations, respectively. Information sufficiency and discovery coverage are also higher than exact optimality for every model.",
      "Observed exact-optimality rates vary substantially across optimization families. Every model records lower exact optimality and reference utility at L4 than at L1, although the intermediate levels are not uniformly monotonic. Workload indexes the executed work of the offline exact methods; it is not a deterministic ranking of LLM difficulty.",
    ],
    diagnosticHeading: "Sufficient information does not guarantee global optimality",
    diagnosticText:
      "For GPT-5.6 Sol, 647 evaluations have trajectories satisfying information sufficiency. Of these, 41.6% reach the global optimum, 56.3% end in a feasible but suboptimal decision, and 2.2% are infeasible. Information sufficiency means that joint normalization of the recorded fact-revealing responses recovers at least one verified sufficient fact set in full; it does not establish that the agent recognized, reconstructed, or correctly used that information.",
    exact: "Exact optimality",
    optimalOutcome: "Globally optimal",
    feasibleSuboptimal: "Feasible but suboptimal",
    infeasible: "Infeasible",
    noDecisionOrProtocol: "No decision or protocol violation",
    leaderboardHeading: "Overall Performance",
    leaderboardIntro:
      "Models are ranked by mean exact optimality across three trials on the same set of 240 algorithmic worlds. Values are the mean ± sample standard deviation of the trial-level summaries.",
    finalDecisionGroup: "Final-decision metrics",
    trajectoryGroup: "Trajectory diagnostics",
    model: "Model",
    feasible: "Feasibility",
    utility: "Reference utility",
    sufficiency: "Information sufficiency",
    discovery: "Discovery coverage",
    errorNote: "Exact optimality, feasibility, information sufficiency, and discovery coverage are percentages; reference utility is reported as 100 × U. Bold marks the highest mean in each metric and does not imply statistical significance.",
  },
  footer: {
    summary: "Evaluating whether LLM agents can turn information acquired through tools into globally optimal decisions.",
    detail: "240 algorithmic worlds built from 120 hidden instances with independently verified optima.",
  },
};
