"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "mod-banner-dismissed";
const MOD_URL =
  "https://steamcommunity.com/sharedfiles/filedetails/?id=3747536911";

// Steam-blue banner announcing the in-game mod on the Steam Workshop. Sits
// under the Overwolf banner and above the admin announcement banner. Dismiss
// is remembered per browser, same pattern as the Overwolf banner.
export default function ModBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      setVisible(true);
    }
  }, []);

  if (!visible) return null;

  return (
    <div className="bg-[#1b2838] border-b border-[#2a475e]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 flex items-center gap-3">
        <img
          src="/steam-logo.svg"
          alt="Steam Workshop"
          className="w-7 h-7 sm:w-8 sm:h-8 flex-shrink-0"
        />
        <p className="flex-1 min-w-0 text-sm text-[#c7d5e0]">
          <span className="font-semibold text-white">
            Spire Codex now has a mod.
          </span>{" "}
          Get it on the Steam Workshop with in-game stats contribution, auto
          uploads, and route planner{" "}
          <a
            href={MOD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-semibold text-[#66c0f4] underline hover:text-white transition-colors"
          >
            here
          </a>
          .
        </p>
        <button
          type="button"
          onClick={() => {
            localStorage.setItem(STORAGE_KEY, "1");
            setVisible(false);
          }}
          aria-label="Dismiss mod banner"
          className="text-[#c7d5e0]/70 hover:text-white transition-colors text-lg leading-none flex-shrink-0"
        >
          &times;
        </button>
      </div>
    </div>
  );
}
