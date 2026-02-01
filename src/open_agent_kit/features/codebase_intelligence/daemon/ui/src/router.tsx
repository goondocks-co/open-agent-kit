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
import Help from "@/pages/Help";
import AgentsLayout from "@/pages/AgentsLayout";
import AgentsList from "@/components/agents/AgentsList";
import RunHistory from "@/components/agents/RunHistory";
import Schedules from "@/components/agents/Schedules";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            { index: true, element: <Dashboard /> },
            // Placeholders for other routes
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
                ]
            },
            { path: "team", element: <Team /> },
            { path: "config", element: <Config /> },
            { path: "help", element: <Help /> },
            { path: "devtools", element: <DevTools /> },
            { path: "*", element: <Navigate to="/" replace /> },
        ],
    },
]);
