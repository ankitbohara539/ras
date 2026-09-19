// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { PublicLanguageProvider, PublicLanguageToggle, usePublicLanguage } from "./public-language";

function TranslatedText() {
  const { text } = usePublicLanguage();
  return <p>{text("Your ward", "तपाईंको वडा")}</p>;
}

describe("public language selection", () => {
  beforeEach(() => localStorage.clear());

  it("switches to Nepali and persists the selection", () => {
    render(
      <PublicLanguageProvider>
        <PublicLanguageToggle />
        <TranslatedText />
      </PublicLanguageProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "नेपाली" }));

    expect(screen.getByText("तपाईंको वडा")).toBeTruthy();
    expect(localStorage.getItem("civicgrid-public-language")).toBe("ne");
    expect(document.documentElement.lang).toBe("ne");
  });
});
