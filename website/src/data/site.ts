import results from "./results.v1.json";

export interface TaskDefinition {
  taskFamilyId: string;
  name: string;
  decision: string;
  instanceData: string;
  method: string;
}

export const siteConfig = {
  title: "AlgoWorlds | Weixin AI",
  organizationName: "Weixin AI",
  brandMark: "brands/weixin-mark.svg",
  resources: {
    paper: {
      label: "Paper (arXiv)",
      href: "https://arxiv.org/abs/2608.29397",
    },
    repository: {
      label: "Code & Dataset",
      href: "https://github.com/xzx34/AlgoWorlds",
    },
  },
  paperFigure: {
    src: "figures/algoworlds-figure-1.png",
    width: 2850,
    height: 816,
    sha256: "2509ed1e2815a5c39224d8487f34d7e420b1424037ebef6664625bb77f9321d8",
  },
} as const;

export const modelProviders: Record<string, string> = {
  "claude-opus-4-8": "Anthropic",
  "claude-sonnet-5": "Anthropic",
  "gpt-5.6-sol": "OpenAI",
  "gpt-5.6-terra": "OpenAI",
  "glm-5.2": "Z.ai",
  "deepseek-v4-pro": "DeepSeek",
  "qwen3.5-plus": "Qwen",
};

export const taskDefinitions: TaskDefinition[] = [
  {
    taskFamilyId: "transit_routing",
    name: "Transit Routing",
    decision: "One route leg per stage",
    instanceData: "Stage-specific legs, travel times, line labels, directed transfer costs, and residues",
    method: "Residue and last-line dynamic program",
  },
  {
    taskFamilyId: "basket_assembly",
    name: "Basket Assembly",
    decision: "A ticket set forming an exact cover",
    instanceData: "Requirements, ticket-item incidence, and prices",
    method: "First-uncovered-item bitmask dynamic program",
  },
  {
    taskFamilyId: "station_siting",
    name: "Station Siting",
    decision: "One site per zone",
    instanceData: "Shared capacity, site costs, and bounded-span pairwise demand rewards",
    method: "Resource-aware band-frontier dynamic program",
  },
  {
    taskFamilyId: "authorization_planning",
    name: "Authorization Planning",
    decision: "A package sequence",
    instanceData: "Authorization relations, policy adjustments, handoffs, and clearance residue",
    method: "Product-state dynamic program",
  },
  {
    taskFamilyId: "series_portfolio",
    name: "Series Portfolio",
    decision: "One lot per title",
    instanceData: "Lot values, scopes, and overlapping signed factors",
    method: "Bounded-span factor dynamic program",
  },
  {
    taskFamilyId: "machine_layout",
    name: "Machine Layout",
    decision: "A machine-to-slot permutation",
    instanceData: "Machine flows, a unit-spaced slot order, and placement adjustments",
    method: "Cut-identity subset dynamic program",
  },
  {
    taskFamilyId: "sequential_matching",
    name: "Sequential Matching",
    decision: "An ordered perfect matching",
    instanceData: "Compatibility, pair costs, and directed handoffs",
    method: "Used-set and last-match dynamic program",
  },
  {
    taskFamilyId: "fleet_dispatch",
    name: "Fleet Dispatch",
    decision: "A job-to-vehicle assignment",
    instanceData: "Job loads, eligible vehicle-job pairs, capacities, route costs, and activation costs",
    method: "Mixed-radix capacity dynamic program",
  },
  {
    taskFamilyId: "evidence_joined_routing",
    name: "Evidence-Joined Routing",
    decision: "A layered source-to-target path",
    instanceData: "Layered graph with source and target, quantities, exceptions, tariffs, and residues",
    method: "Expanded-state shortest path",
  },
  {
    taskFamilyId: "migration_portfolio",
    name: "Migration Portfolio",
    decision: "One package per component group and an activated domain set",
    instanceData: "Package costs, support domains, activation costs, and signed interactions",
    method: "Activated-domain mask enumeration",
  },
];

export { results };
