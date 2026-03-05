import { createBrowserRouter, Navigate } from "react-router-dom";
import Layout from "./layouts/Layout";
import Dashboard from "./pages/Dashboard";
import SearchPage from "./pages/Search";
import Nodes from "./pages/Nodes";
import Deploy from "./pages/Deploy";
import Agents from "./pages/Agents";
import Logs from "./pages/Logs";
import Config from "./pages/Config";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            { index: true, element: <Dashboard /> },
            { path: "search", element: <SearchPage /> },
            { path: "nodes", element: <Nodes /> },
            { path: "deploy", element: <Deploy /> },
            { path: "agents", element: <Agents /> },
            { path: "logs", element: <Logs /> },
            { path: "config", element: <Config /> },
            { path: "*", element: <Navigate to="/" replace /> },
        ],
    },
]);
