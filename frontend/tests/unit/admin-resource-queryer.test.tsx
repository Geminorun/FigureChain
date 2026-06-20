import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminResourceQueryer } from "@/components/admin-resource-queryer";
import type {
  AdminResourceListResponse,
  AdminResourceQueryResponse,
} from "@/lib/figure-chain-types";
import { renderUi } from "@/test/render";

const runQueryMock = vi.hoisted(() => vi.fn());
const resetMock = vi.hoisted(() => vi.fn());
const hookState = vi.hoisted(() => ({
  resources: null as AdminResourceListResponse | null,
  query: null as AdminResourceQueryResponse | null,
}));

vi.mock("@/hooks/use-admin-resources", () => ({
  useAdminResources: () => ({
    data: hookState.resources,
    error: null,
    loading: false,
    refresh: vi.fn(),
  }),
  useAdminResourceQuery: () => ({
    data: hookState.query,
    error: null,
    loading: false,
    runQuery: runQueryMock,
    reset: resetMock,
  }),
}));

const resources: AdminResourceListResponse = {
  resources: [
    {
      name: "persons",
      label: "人物",
      primary_key: "id",
      default_order_by: "id",
      default_order_direction: "asc",
      columns: [
        {
          key: "id",
          label: "id",
          type: "uuid",
          operators: ["eq", "in"],
          selectable: true,
          filterable: true,
          sortable: true,
          default_selected: true,
          link: "person",
        },
        {
          key: "primary_name_zh_hant",
          label: "primary_name_zh_hant",
          type: "string",
          operators: ["eq", "ilike"],
          selectable: true,
          filterable: true,
          sortable: true,
          default_selected: true,
          link: null,
        },
        {
          key: "birth_year",
          label: "birth_year",
          type: "integer",
          operators: ["eq", "gte", "lte"],
          selectable: true,
          filterable: true,
          sortable: true,
          default_selected: false,
          link: null,
        },
      ],
    },
  ],
};

describe("AdminResourceQueryer", () => {
  beforeEach(() => {
    hookState.resources = resources;
    hookState.query = null;
    runQueryMock.mockReset();
    resetMock.mockReset();
  });

  it("shows resource selector and default selected columns", async () => {
    renderUi(<AdminResourceQueryer />);

    expect(screen.getByLabelText("资源")).toHaveValue("persons");
    await waitFor(() => {
      expect(screen.getByLabelText("id")).toBeChecked();
      expect(screen.getByLabelText("primary_name_zh_hant")).toBeChecked();
      expect(screen.getByLabelText("birth_year")).not.toBeChecked();
    });
  });

  it("adds filter controls and submits a structured query", async () => {
    renderUi(<AdminResourceQueryer />);

    await userEvent.click(screen.getByRole("button", { name: "添加条件" }));
    expect(screen.getByLabelText("条件字段 1")).toBeInTheDocument();
    expect(screen.getByLabelText("条件操作符 1")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("条件值 1"), "蘇");
    await userEvent.click(screen.getByRole("button", { name: "查询资源" }));

    expect(runQueryMock).toHaveBeenCalledWith({
      resource: "persons",
      select: ["id", "primary_name_zh_hant"],
      filters: [{ field: "id", operator: "eq", value: "蘇" }],
      order_by: "id",
      order_direction: "asc",
      limit: 50,
      offset: 0,
    });
  });

  it("renders linked values and CLI preview", () => {
    hookState.query = {
      resource: "persons",
      columns: resources.resources[0].columns.slice(0, 2),
      rows: [{ id: "person-1", primary_name_zh_hant: "蘇軾" }],
      limit: 50,
      offset: 0,
      preview: "resource=persons select=id,primary_name_zh_hant",
    };

    renderUi(<AdminResourceQueryer />);

    expect(screen.getByRole("link", { name: "person-1" })).toHaveAttribute(
      "href",
      "/people/person-1",
    );
    expect(screen.getByText("蘇軾")).toBeInTheDocument();
    expect(
      screen.getByText("resource=persons select=id,primary_name_zh_hant"),
    ).toBeInTheDocument();
  });
});
