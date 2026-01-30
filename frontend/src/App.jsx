import React from "react";
import VideoForm from "./components/VideoForm.jsx";

export default function App() {
  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <header>
        <h1 className="text-3xl font-bold">AI Text → Video</h1>
        <p className="text-slate-300">Split script to scenes, choose AI or upload backgrounds, render & download.</p>
      </header>
      <VideoForm />
    </div>
  );
}
