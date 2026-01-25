import { createBrowserRouter, Navigate } from "react-router-dom";
import { Layout } from "@/layouts/Layout";
import Dashboard from "@/pages/Dashboard";
import Logs from "@/pages/Logs";
import Search from "@/pages/Search";
import DataExplorer from "@/pages/DataExplorer";
import SessionList from "@/components/data/SessionList";
import PlansList from "@/components/data/PlansList";
import MemoriesList from "@/components/data/MemoriesList";
import SessionDetail from "@/pages/SessionDetail";
import Config from "@/pages/Config";
import DevTools from "@/pages/DevTools";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            { index: true, element: <Dashboard /> },
            // Placeholders for other routes
            { path: "search", element: <Search /> },
            {
                path: "data",
                element: <DataExplorer />,
                children: [
                    { index: true, element: <Navigate to="sessions" replace /> },
                    { path: "sessions", element: <SessionList /> },
                    { path: "plans", element: <PlansList /> },
                    { path: "memories", element: <MemoriesList /> },
                ]
            },
            { path: "data/sessions/:id", element: <SessionDetail /> },
            { path: "logs", element: <Logs /> },
            { path: "config", element: <Config /> },
            { path: "devtools", element: <DevTools /> },
            { path: "*", element: <Navigate to="/" replace /> },
        ],
    },
]);
