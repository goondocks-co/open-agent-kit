import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "@/layouts/Layout";
import Dashboard from "@/pages/Dashboard";
import Logs from "@/pages/Logs";
import Search from "@/pages/Search";
import Activity from "@/pages/Activity";
import SessionList from "@/components/data/SessionList";
import PlansList from "@/components/data/PlansList";
import MemoriesList from "@/components/data/MemoriesList";
import SessionDetail from "@/pages/SessionDetail";
import Config from "@/pages/Config";
import DevTools from "@/pages/DevTools";
import Team from "@/pages/Team";
import TeamRelay from "@/components/team/TeamRelay";
import TeamMembers from "@/components/team/TeamMembers";
import TeamPolicy from "@/components/team/TeamPolicy";
import TeamBackups from "@/components/team/TeamBackups";
import Help from "@/pages/Help";
import AgentsLayout from "@/pages/AgentsLayout";
import AgentsList from "@/components/agents/AgentsList";
import RunHistory from "@/components/agents/RunHistory";
import Schedules from "@/components/agents/Schedules";
import AgentSettings from "@/pages/AgentSettings";
import ACPIntegrations from "@/components/agents/ACPIntegrations";
import Governance from "@/pages/Governance";
import GovernanceAudit from "@/components/governance/GovernanceAudit";
import GovernanceRules from "@/components/governance/GovernanceRules";


export const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            { index: true, element: <Dashboard /> },
            { path: "search", element: <Search /> },
            {
                path: "activity",
                element: <Activity />,
                children: [
                    { index: true, element: <Navigate to="sessions" replace /> },
                    { path: "sessions", element: <SessionList /> },
                    { path: "plans", element: <PlansList /> },
                    { path: "memories", element: <MemoriesList /> },
                ]
            },
            { path: "activity/sessions/:id", element: <SessionDetail /> },
            { path: "logs", element: <Logs /> },
            {
                path: "agents",
                element: <AgentsLayout />,
                children: [
                    { index: true, element: <AgentsList /> },
                    { path: "runs", element: <RunHistory /> },
                    { path: "schedules", element: <Schedules /> },
                    { path: "settings", element: <AgentSettings /> },
                    { path: "integrations", element: <ACPIntegrations /> },
                ]
            },
            // Legacy redirects
            { path: "cloud", element: <Navigate to="/team/relay" replace /> },
            {
                path: "governance",
                element: <Governance />,
                children: [
                    { index: true, element: <Navigate to="audit" replace /> },
                    { path: "audit", element: <GovernanceAudit /> },
                    { path: "rules", element: <GovernanceRules /> },
                ],
            },
            {
                path: "team",
                element: <Team />,
                children: [
                    { index: true, element: <Navigate to="relay" replace /> },
                    { path: "relay", element: <TeamRelay /> },
                    { path: "members", element: <TeamMembers /> },
                    { path: "policy", element: <TeamPolicy /> },
                    { path: "backups", element: <TeamBackups /> },
                    // Legacy redirects
                    { path: "status", element: <Navigate to="/team/relay" replace /> },
                    { path: "config", element: <Navigate to="/team/relay" replace /> },
                    { path: "connectivity", element: <Navigate to="/team/relay" replace /> },
                    { path: "sharing", element: <Navigate to="/team/relay" replace /> },
                ]
            },
            { path: "config", element: <Config /> },
            { path: "help", element: <Help /> },
            { path: "devtools", element: <DevTools /> },
            { path: "*", element: <Navigate to="/" replace /> },
        ],
    },
]);
