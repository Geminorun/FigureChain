import type { ReactElement } from "react";
import { render, type RenderOptions } from "@testing-library/react";

export function renderUi(ui: ReactElement, options?: RenderOptions) {
  return render(ui, options);
}
