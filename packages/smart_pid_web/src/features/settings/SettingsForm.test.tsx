import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, afterEach } from "vitest";
import { SettingsForm } from "./SettingsForm";

afterEach(() => localStorage.clear());

describe("SettingsForm", () => {
  it("renders the preference controls", () => {
    render(<SettingsForm />);
    expect(screen.getByLabelText(/number decimals/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/trend window/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm destructive/i)).toBeInTheDocument();
  });

  it("updates a preference when the user edits it", () => {
    render(<SettingsForm />);
    const decimals = screen.getByLabelText(/number decimals/i) as HTMLInputElement;
    fireEvent.change(decimals, { target: { value: "3" } });
    expect(decimals.value).toBe("3");
    expect(JSON.parse(localStorage.getItem("spid.preferences")!).numberDecimals).toBe(3);
  });

  it("does NOT render any admin password or user-management control", () => {
    render(<SettingsForm />);
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/manage users/i)).not.toBeInTheDocument();
  });
});
