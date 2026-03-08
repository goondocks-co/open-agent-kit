import { createBrowserRouter, Navigate } from "react-router-dom";
import Layout from "./layouts/Layout";
import Dashboard from "./pages/Dashboard";
import SearchPage from "./pages/Search";
import Nodes from "./pages/Nodes";
import Connect from "./pages/Connect";
import Deploy from "./pages/Deploy";
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
            { path: "connect", element: <Connect /> },
            { path: "deploy", element: <Deploy /> },
            { path: "logs", element: <Logs /> },
            { path: "config", element: <Config /> },
            { path: "*", element: <Navigate to="/" replace /> },
        ],
    },
]);
