import React from "react";
import { createRoot } from "react-dom/client";

function App() {
  return <h1>Hello from the sample React app!</h1>;
}

const rootElement = document.getElementById("root");
const root = createRoot(rootElement);
root.render(<App />);
