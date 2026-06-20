"use client";

import { useCallback, useMemo, useState } from "react";

import { AdminResourceResultsTable } from "@/components/admin-resource-results-table";
import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import {
  useAdminResourceQuery,
  useAdminResources,
} from "@/hooks/use-admin-resources";
import type {
  AdminResource,
  AdminResourceColumn,
  AdminResourceFilterRequest,
} from "@/lib/figure-chain-types";

type FilterRow = {
  id: number;
  field: string;
  operator: string;
  value: string;
};

function defaultSelectedColumns(resource: AdminResource): string[] {
  return resource.columns
    .filter((column) => column.default_selected && column.selectable)
    .map((column) => column.key);
}

function filterableColumns(resource: AdminResource): AdminResourceColumn[] {
  return resource.columns.filter((column) => column.filterable);
}

function sortableColumns(resource: AdminResource): AdminResourceColumn[] {
  return resource.columns.filter((column) => column.sortable);
}

function makeDefaultFilter(resource: AdminResource, id: number): FilterRow | null {
  const firstColumn = filterableColumns(resource)[0];
  if (!firstColumn) {
    return null;
  }
  return {
    id,
    field: firstColumn.key,
    operator: firstColumn.operators[0] ?? "eq",
    value: "",
  };
}

function isValueOperator(operator: string): boolean {
  return operator !== "is_null" && operator !== "is_not_null";
}

export function AdminResourceQueryer() {
  const resources = useAdminResources();
  const query = useAdminResourceQuery();
  const [selectedResourceName, setSelectedResourceName] = useState("");
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [filters, setFilters] = useState<FilterRow[]>([]);
  const [nextFilterId, setNextFilterId] = useState(1);
  const [orderBy, setOrderBy] = useState("");
  const [orderDirection, setOrderDirection] = useState<"asc" | "desc">("asc");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  const resourceList = useMemo(
    () => resources.data?.resources ?? [],
    [resources.data],
  );
  const effectiveResourceName = selectedResourceName || resourceList[0]?.name || "";
  const selectedResource = useMemo(
    () => resourceList.find((resource) => resource.name === effectiveResourceName) ?? null,
    [effectiveResourceName, resourceList],
  );
  const activeSelectedColumns =
    selectedColumns.length > 0 || !selectedResource
      ? selectedColumns
      : defaultSelectedColumns(selectedResource);
  const activeOrderBy =
    orderBy || selectedResource?.default_order_by || "";
  const activeOrderDirection =
    orderBy || !selectedResource
      ? orderDirection
      : selectedResource.default_order_direction;

  const selectResource = useCallback((resource: AdminResource) => {
    setSelectedResourceName(resource.name);
    setSelectedColumns(defaultSelectedColumns(resource));
    setFilters([]);
    setOrderBy(resource.default_order_by);
    setOrderDirection(resource.default_order_direction);
    setLimit(50);
    setOffset(0);
    query.reset();
  }, [query]);

  function toggleColumn(columnKey: string) {
    const base = activeSelectedColumns;
    setSelectedColumns(
      base.includes(columnKey)
        ? base.filter((key) => key !== columnKey)
        : [...base, columnKey],
    );
  }

  function addFilter() {
    if (!selectedResource) {
      return;
    }
    const nextFilter = makeDefaultFilter(selectedResource, nextFilterId);
    if (!nextFilter) {
      return;
    }
    setFilters((current) => [...current, nextFilter]);
    setNextFilterId((current) => current + 1);
  }

  function updateFilter(id: number, patch: Partial<FilterRow>) {
    setFilters((current) =>
      current.map((filter) => {
        if (filter.id !== id) {
          return filter;
        }
        const next = { ...filter, ...patch };
        const nextColumn = selectedResource?.columns.find(
          (column) => column.key === next.field,
        );
        if (patch.field && nextColumn) {
          next.operator = nextColumn.operators[0] ?? "eq";
          next.value = "";
        }
        return next;
      }),
    );
  }

  function removeFilter(id: number) {
    setFilters((current) => current.filter((filter) => filter.id !== id));
  }

  function submitQuery() {
    if (!selectedResource) {
      return;
    }
    const requestFilters: AdminResourceFilterRequest[] = filters.map((filter) => ({
      field: filter.field,
      operator: filter.operator,
      value: isValueOperator(filter.operator) ? filter.value : null,
    }));
    void query.runQuery({
      resource: selectedResource.name,
      select: activeSelectedColumns,
      filters: requestFilters,
      order_by: activeOrderBy || selectedResource.default_order_by,
      order_direction: activeOrderDirection,
      limit,
      offset,
    });
  }

  if (resources.loading && !resources.data) {
    return (
      <p className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        正在加载资源定义...
      </p>
    );
  }

  if (resources.error) {
    return <ErrorCallout error={resources.error} />;
  }

  if (resourceList.length === 0) {
    return (
      <EmptyState
        description="后端未返回任何可查询资源。"
        title="暂无资源定义"
      />
    );
  }

  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(24rem,0.8fr)_minmax(0,1.2fr)]">
      <form
        className="space-y-4 rounded border border-stone-200 bg-white p-4"
        onSubmit={(event) => {
          event.preventDefault();
          submitQuery();
        }}
      >
        <div className="border-b border-stone-200 pb-3">
          <p className="text-sm font-medium text-amber-700">资源查询器</p>
          <h2 className="mt-1 text-xl font-semibold text-stone-950">
            白名单资源查询
          </h2>
          <p className="mt-1 text-sm text-stone-600">
            只能查询后端注册表中的资源、字段和操作符，不接受 SQL 文本。
          </p>
        </div>

        <label className="block text-sm font-medium text-stone-800">
          资源
          <select
            aria-label="资源"
            className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
            value={effectiveResourceName}
            onChange={(event) => {
              const next = resourceList.find(
                (resource) => resource.name === event.target.value,
              );
              if (next) {
                selectResource(next);
              }
            }}
          >
            {resourceList.map((resource) => (
              <option key={resource.name} value={resource.name}>
                {resource.label}
              </option>
            ))}
          </select>
        </label>

        {selectedResource ? (
          <>
            <fieldset className="border-t border-stone-200 pt-3">
              <legend className="text-sm font-semibold text-stone-950">
                显示字段
              </legend>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {selectedResource.columns
                  .filter((column) => column.selectable)
                  .map((column) => (
                    <label
                      className="flex items-center gap-2 text-sm text-stone-700"
                      key={column.key}
                    >
                      <input
                        aria-label={column.label}
                        checked={activeSelectedColumns.includes(column.key)}
                        type="checkbox"
                        onChange={() => toggleColumn(column.key)}
                      />
                      <span className="font-mono text-xs">{column.label}</span>
                    </label>
                  ))}
              </div>
            </fieldset>

            <fieldset className="space-y-3 border-t border-stone-200 pt-3">
              <legend className="text-sm font-semibold text-stone-950">
                查询条件
              </legend>
              {filters.map((filter, index) => {
                const column = selectedResource.columns.find(
                  (item) => item.key === filter.field,
                );
                return (
                  <div
                    className="grid gap-2 rounded border border-stone-200 p-3 sm:grid-cols-[1fr_1fr_1fr_auto]"
                    key={filter.id}
                  >
                    <label className="text-sm font-medium text-stone-800">
                      字段
                      <select
                        aria-label={`条件字段 ${index + 1}`}
                        className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
                        value={filter.field}
                        onChange={(event) =>
                          updateFilter(filter.id, { field: event.target.value })
                        }
                      >
                        {filterableColumns(selectedResource).map((item) => (
                          <option key={item.key} value={item.key}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-sm font-medium text-stone-800">
                      操作符
                      <select
                        aria-label={`条件操作符 ${index + 1}`}
                        className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
                        value={filter.operator}
                        onChange={(event) =>
                          updateFilter(filter.id, {
                            operator: event.target.value,
                            value: "",
                          })
                        }
                      >
                        {(column?.operators ?? []).map((operator) => (
                          <option key={operator} value={operator}>
                            {operator}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="text-sm font-medium text-stone-800">
                      值
                      <input
                        aria-label={`条件值 ${index + 1}`}
                        className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm disabled:bg-stone-100"
                        disabled={!isValueOperator(filter.operator)}
                        value={filter.value}
                        onChange={(event) =>
                          updateFilter(filter.id, { value: event.target.value })
                        }
                      />
                    </label>
                    <button
                      className="self-end rounded border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-100"
                      onClick={() => removeFilter(filter.id)}
                      type="button"
                    >
                      移除
                    </button>
                  </div>
                );
              })}
              <button
                className="rounded border border-stone-300 px-3 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100"
                onClick={addFilter}
                type="button"
              >
                添加条件
              </button>
            </fieldset>

            <fieldset className="grid gap-3 border-t border-stone-200 pt-3 sm:grid-cols-4">
              <legend className="text-sm font-semibold text-stone-950">
                排序与分页
              </legend>
              <label className="text-sm font-medium text-stone-800">
                排序字段
                <select
                  aria-label="排序字段"
                  className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
                  value={activeOrderBy}
                  onChange={(event) => setOrderBy(event.target.value)}
                >
                  {sortableColumns(selectedResource).map((column) => (
                    <option key={column.key} value={column.key}>
                      {column.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-stone-800">
                排序方向
                <select
                  aria-label="排序方向"
                  className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
                  value={activeOrderDirection}
                  onChange={(event) =>
                    setOrderDirection(event.target.value as "asc" | "desc")
                  }
                >
                  <option value="asc">升序</option>
                  <option value="desc">降序</option>
                </select>
              </label>
              <label className="text-sm font-medium text-stone-800">
                每页数量
                <input
                  aria-label="每页数量"
                  className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
                  max={200}
                  min={1}
                  type="number"
                  value={limit}
                  onChange={(event) => setLimit(Number(event.target.value))}
                />
              </label>
              <label className="text-sm font-medium text-stone-800">
                偏移
                <input
                  aria-label="偏移"
                  className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm"
                  min={0}
                  type="number"
                  value={offset}
                  onChange={(event) => setOffset(Number(event.target.value))}
                />
              </label>
            </fieldset>

            <button
              className="min-h-10 w-full rounded bg-stone-950 px-4 py-2 text-sm font-semibold text-white hover:bg-stone-800 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={query.loading || activeSelectedColumns.length === 0}
              type="submit"
            >
              查询资源
            </button>
          </>
        ) : null}
      </form>

      <section className="space-y-4">
        {query.error ? <ErrorCallout error={query.error} /> : null}
        {query.loading ? (
          <p className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
            正在查询资源...
          </p>
        ) : null}
        {query.data ? (
          <>
            <div className="rounded border border-stone-200 bg-white p-4">
              <p className="text-sm font-semibold text-stone-950">CLI 预览</p>
              <code className="mt-2 block break-words rounded bg-stone-100 p-3 text-xs text-stone-800">
                {query.data.preview}
              </code>
            </div>
            <AdminResourceResultsTable
              columns={query.data.columns}
              rows={query.data.rows}
            />
          </>
        ) : (
          <EmptyState
            description="选择资源、字段和条件后执行查询。"
            title="尚未执行查询"
          />
        )}
      </section>
    </section>
  );
}
