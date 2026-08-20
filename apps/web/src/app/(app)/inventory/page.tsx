"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { motion } from "framer-motion";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCreateInventoryCategory,
  useCreateInventoryItem,
  useInventoryCategories,
  useInventoryItems,
  useRecordStockMovement,
  useStockMovements,
  useUpdateInventoryItem,
} from "@/hooks/use-api";

const categorySchema = z.object({
  name: z.string().min(1, "Name required"),
  description: z.string().optional(),
});
type CategoryForm = z.infer<typeof categorySchema>;

const itemSchema = z.object({
  name: z.string().min(1, "Name required"),
  category_id: z.string().optional(),
  sku: z.string().optional(),
  quantity: z.coerce.number().min(0),
  unit: z.string().optional(),
  unit_cost: z.coerce.number().min(0),
  low_stock_threshold: z.coerce.number().min(0),
  notes: z.string().optional(),
});
type ItemForm = z.infer<typeof itemSchema>;

const movementSchema = z.object({
  item_id: z.string().min(1, "Choose an item"),
  movement_type: z.enum(["restock", "issue"]),
  delta: z.coerce.number().positive("Delta must be > 0"),
  reason: z.string().optional(),
});
type MovementForm = z.infer<typeof movementSchema>;

const currency = (v: number) => `₦${v.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

export default function InventoryPage() {
  const { data: items = [], isLoading: loadingItems } = useInventoryItems();
  const { data: categories = [] } = useInventoryCategories();
  const [showItemForm, setShowItemForm] = useState(false);
  const [editingItem, setEditingItem] = useState<string | null>(null);
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [historyItemId, setHistoryItemId] = useState<string | null>(null);

  const createCategory = useCreateInventoryCategory();
  const createItem = useCreateInventoryItem();
  const updateItem = useUpdateInventoryItem();
  const recordMovement = useRecordStockMovement();
  const { data: movements = [] } = useStockMovements(historyItemId);

  const {
    register: regCategory,
    handleSubmit: submitCategory,
    reset: resetCategory,
    formState: { errors: categoryErrors, isSubmitting: categorySubmitting },
  } = useForm<CategoryForm>({ resolver: zodResolver(categorySchema) });

  const {
    register: regItem,
    handleSubmit: submitItem,
    reset: resetItem,
    formState: { errors: itemErrors, isSubmitting: itemSubmitting },
  } = useForm<ItemForm>({ resolver: zodResolver(itemSchema) });

  const {
    register: regMovement,
    handleSubmit: submitMovement,
    reset: resetMovement,
    formState: { errors: movementErrors, isSubmitting: movementSubmitting },
  } = useForm<MovementForm>({ resolver: zodResolver(movementSchema) });

  const historyItem = items.find((i) => i.id === historyItemId) ?? null;
  const lowStock = items.filter((i) => i.quantity <= i.low_stock_threshold);
  const totalValue = items.reduce((sum, i) => sum + i.quantity * i.unit_cost, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Inventory</h1>
          <p className="text-sm text-muted-foreground">
            Track {items.length} items worth {currency(totalValue)} across {categories.length} categories.
          </p>
        </div>
        <Button onClick={() => { setEditingItem(null); setShowItemForm((v) => !v); }}>
          <Plus className="h-4 w-4" /> Add item
        </Button>
      </div>

      {lowStock.length > 0 && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
          <span className="font-semibold text-amber-600">{lowStock.length} item{lowStock.length > 1 ? "s" : ""} below the low-stock threshold.</span>
        </div>
      )}

      {/* Items */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Items</CardTitle>
            <Button variant="outline" size="sm" onClick={() => setShowCategoryForm((v) => !v)}>
              {showCategoryForm ? "Close" : "Add category"}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {showCategoryForm && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <form
                onSubmit={submitCategory((v) => {
                  createCategory.mutate({ ...v, description: v.description || null }, {
                    onSuccess: () => { resetCategory(); setShowCategoryForm(false); },
                  });
                })}
                className="flex flex-wrap items-end gap-4 rounded-md border p-4"
              >
                <div className="space-y-2">
                  <Label>Category name</Label>
                  <Input placeholder="Stationery" className="w-56" {...regCategory("name")} />
                  {categoryErrors.name && <p className="text-xs text-destructive">{categoryErrors.name.message}</p>}
                </div>
                <div className="flex-1 space-y-2">
                  <Label>Description</Label>
                  <Input placeholder="Optional" {...regCategory("description")} />
                </div>
                <Button type="submit" disabled={categorySubmitting}>
                  {categorySubmitting ? "Saving…" : "Create"}
                </Button>
              </form>
            </motion.div>
          )}

          {showItemForm && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <form
                onSubmit={submitItem((v) => {
                  const payload = {
                    ...v,
                    category_id: v.category_id || null,
                    sku: v.sku || null,
                    unit: v.unit || null,
                    notes: v.notes || null,
                    is_active: true,
                  };
                  const onSuccess = () => { resetItem(); setShowItemForm(false); setEditingItem(null); };
                  if (editingItem) {
                    updateItem.mutate({ itemId: editingItem, input: payload }, { onSuccess });
                  } else {
                    createItem.mutate(payload, { onSuccess });
                  }
                })}
                className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4"
              >
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input placeholder="Exercise books" {...regItem("name")} />
                  {itemErrors.name && <p className="text-xs text-destructive">{itemErrors.name.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regItem("category_id")}>
                    <option value="">None</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div className="space-y-2">
                  <Label>SKU</Label>
                  <Input placeholder="SKU-001" {...regItem("sku")} />
                </div>
                <div className="space-y-2">
                  <Label>Unit</Label>
                  <Input placeholder="pcs" {...regItem("unit")} />
                </div>
                <div className="space-y-2">
                  <Label>Quantity</Label>
                  <Input type="number" step="0.01" placeholder="100" {...regItem("quantity")} />
                </div>
                <div className="space-y-2">
                  <Label>Unit cost</Label>
                  <Input type="number" step="0.01" placeholder="500" {...regItem("unit_cost")} />
                </div>
                <div className="space-y-2">
                  <Label>Low stock threshold</Label>
                  <Input type="number" step="0.01" placeholder="10" {...regItem("low_stock_threshold")} />
                </div>
                <div className="flex items-end gap-2">
                  <Button type="submit" disabled={itemSubmitting}>
                    {itemSubmitting ? "Saving…" : editingItem ? "Update" : "Create"}
                  </Button>
                  {editingItem && <Button type="button" variant="ghost" onClick={() => { setEditingItem(null); resetItem(); setShowItemForm(false); }}>Cancel</Button>}
                </div>
              </form>
            </motion.div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Item</th>
                  <th className="pb-2 font-medium">Category</th>
                  <th className="pb-2 font-medium text-right">Stock</th>
                  <th className="pb-2 font-medium text-right">Unit cost</th>
                  <th className="pb-2 font-medium text-right">Value</th>
                  <th className="pb-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loadingItems ? (
                  <tr><td colSpan={6}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                ) : items.length === 0 ? (
                  <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">
                    No inventory items yet. Add one above.
                  </td></tr>
                ) : (
                  items.map((i) => {
                    const isLow = i.quantity <= i.low_stock_threshold;
                    return (
                      <tr key={i.id} className="border-b last:border-0 hover:bg-accent/40">
                        <td className="py-2.5">
                          <p className="font-medium">{i.name}</p>
                          {i.sku && <p className="font-mono text-xs text-muted-foreground">{i.sku}</p>}
                        </td>
                        <td className="py-2.5">{i.category_name ?? "—"}</td>
                        <td className={`py-2.5 text-right font-medium ${isLow ? "text-amber-600" : "text-emerald-600"}`}>
                          {i.quantity} {i.unit ?? ""}
                          {isLow && <span className="ml-1 text-xs normal-case text-amber-600">low</span>}
                        </td>
                        <td className="py-2.5 text-right">{currency(i.unit_cost)}</td>
                        <td className="py-2.5 text-right">{currency(i.quantity * i.unit_cost)}</td>
                        <td className="py-2.5 text-right">
                          <div className="flex justify-end gap-2">
                            <Button variant="ghost" size="sm" onClick={() => setHistoryItemId(i.id)}>History</Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setEditingItem(i.id);
                                setShowItemForm(true);
                                resetItem({
                                  name: i.name,
                                  category_id: i.category_id ?? "",
                                  sku: i.sku ?? "",
                                  quantity: i.quantity,
                                  unit: i.unit ?? "",
                                  unit_cost: i.unit_cost,
                                  low_stock_threshold: i.low_stock_threshold,
                                  notes: i.notes ?? "",
                                });
                              }}
                            >
                              Edit
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Stock movement */}
      <Card>
        <CardHeader>
          <CardTitle>Stock adjustment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form
            onSubmit={submitMovement((v) => {
              recordMovement.mutate(
                { item_id: v.item_id, movement_type: v.movement_type, delta: v.delta, reason: v.reason || null },
                { onSuccess: () => { resetMovement(); setHistoryItemId(v.item_id); } },
              );
            })}
            className="flex flex-wrap items-end gap-4 rounded-md border p-4"
          >
            <div className="space-y-2">
              <Label>Item</Label>
              <select className="h-9 w-56 rounded-md border border-input bg-transparent px-3 text-sm" {...regMovement("item_id")}>
                <option value="">Choose…</option>
                {items.map((i) => (
                  <option key={i.id} value={i.id}>{i.name} — {i.quantity} {i.unit ?? ""}</option>
                ))}
              </select>
              {movementErrors.item_id && <p className="text-xs text-destructive">{movementErrors.item_id.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Type</Label>
              <select className="h-9 w-32 rounded-md border border-input bg-transparent px-3 text-sm" {...regMovement("movement_type")}>
                <option value="restock">Restock (+)</option>
                <option value="issue">Issue (−)</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Quantity</Label>
              <Input type="number" step="0.01" className="w-28" placeholder="5" {...regMovement("delta")} />
              {movementErrors.delta && <p className="text-xs text-destructive">{movementErrors.delta.message}</p>}
            </div>
            <div className="flex-1 space-y-2">
              <Label>Reason</Label>
              <Input placeholder="Optional note" {...regMovement("reason")} />
            </div>
            <Button type="submit" disabled={movementSubmitting || recordMovement.isPending}>
              {movementSubmitting ? "Applying…" : "Apply"}
            </Button>
          </form>

          {historyItem && (
            <div className="rounded-md border p-4">
              <h3 className="mb-3 text-sm font-semibold">Movement history — {historyItem.name}</h3>
              {movements.length === 0 ? (
                <p className="text-sm text-muted-foreground">No movements recorded yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="pb-2 font-medium">Type</th>
                        <th className="pb-2 font-medium text-right">Delta</th>
                        <th className="pb-2 font-medium">Reason</th>
                        <th className="pb-2 font-medium">When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {movements.map((m) => (
                        <tr key={m.id} className="border-b last:border-0">
                          <td className="py-2 capitalize">
                            <span className={`rounded-full px-2 py-0.5 text-xs ${m.movement_type === "restock" ? "bg-emerald-500/15 text-emerald-600" : "bg-rose-500/15 text-rose-600"}`}>
                              {m.movement_type}
                            </span>
                          </td>
                          <td className={`py-2 text-right font-medium ${m.delta > 0 ? "text-emerald-600" : "text-rose-600"}`}>
                            {m.delta > 0 ? "+" : ""}{m.delta}
                          </td>
                          <td className="py-2">{m.reason ?? "—"}</td>
                          <td className="py-2 text-muted-foreground">{new Date(m.created_at).toLocaleString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}