import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Providers } from "@/app/providers";

describe("Providers", () => {
  it("renders children inside the query, tooltip and toast providers", () => {
    render(
      <Providers>
        <p>inside providers</p>
      </Providers>,
    );
    expect(screen.getByText("inside providers")).toBeInTheDocument();
  });
});
