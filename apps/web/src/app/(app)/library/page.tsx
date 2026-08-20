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
  useBooks,
  useBorrowings,
  useCheckOutBook,
  useCreateBook,
  useReturnBook,
  useStaff,
  useStudents,
  useUpdateBook,
} from "@/hooks/use-api";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function inDays(days: number) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const bookSchema = z.object({
  title: z.string().min(1, "Title required"),
  author: z.string().optional(),
  isbn: z.string().optional(),
  category: z.string().optional(),
  publisher: z.string().optional(),
  year: z.coerce.number().int().min(1000).max(3000).optional(),
  total_copies: z.coerce.number().int().min(1).default(1),
});
type BookForm = z.infer<typeof bookSchema>;

const borrowSchema = z.object({
  book_id: z.string().min(1, "Choose a book"),
  borrower_type: z.enum(["student", "staff"]),
  student_id: z.string().optional(),
  staff_id: z.string().optional(),
  due_on: z.string().min(1, "Due date required"),
});
type BorrowForm = z.infer<typeof borrowSchema>;

export default function LibraryPage() {
  const { data: books = [], isLoading: loadingBooks } = useBooks();
  const { data: borrowings = [] } = useBorrowings();
  const overdue = useBorrowings({ overdue: true });
  const { data: students = [] } = useStudents();
  const { data: staff = [] } = useStaff();
  const [showBookForm, setShowBookForm] = useState(false);
  const [editingBook, setEditingBook] = useState<string | null>(null);

  const createBook = useCreateBook();
  const updateBook = useUpdateBook();
  const checkOut = useCheckOutBook();
  const returnBk = useReturnBook();

  const {
    register: regBook,
    handleSubmit: submitBook,
    reset: resetBook,
    formState: { errors: bookErrors, isSubmitting: bookSubmitting },
  } = useForm<BookForm>({ resolver: zodResolver(bookSchema) });

  const {
    register: regBorrow,
    handleSubmit: submitBorrow,
    reset: resetBorrow,
    formState: { errors: borrowErrors, isSubmitting: borrowSubmitting },
  } = useForm<BorrowForm>({ resolver: zodResolver(borrowSchema) });

  const onLoan = books.reduce((n, b) => n + (b.total_copies - b.available_copies), 0);
  const overdueCount = overdue.data?.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Library</h1>
          <p className="text-sm text-muted-foreground">
            {books.length} titles, {onLoan} on loan, {overdueCount} overdue.
          </p>
        </div>
        <Button onClick={() => { setEditingBook(null); setShowBookForm((v) => !v); }}>
          <Plus className="h-4 w-4" /> Add book
        </Button>
      </div>

      {/* Catalogue */}
      <Card>
        <CardHeader>
          <CardTitle>Catalogue</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {showBookForm && (
            <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <form
                onSubmit={submitBook((v) => {
                  const payload = {
                    ...v,
                    author: v.author || null,
                    isbn: v.isbn || null,
                    category: v.category || null,
                    publisher: v.publisher || null,
                    year: v.year || null,
                    is_active: true,
                  };
                  const onSuccess = () => { resetBook(); setShowBookForm(false); setEditingBook(null); };
                  if (editingBook) {
                    updateBook.mutate({ bookId: editingBook, input: payload }, { onSuccess });
                  } else {
                    createBook.mutate(payload, { onSuccess });
                  }
                })}
                className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-4"
              >
                <div className="space-y-2">
                  <Label>Title</Label>
                  <Input placeholder="Advanced Physics" {...regBook("title")} />
                  {bookErrors.title && <p className="text-xs text-destructive">{bookErrors.title.message}</p>}
                </div>
                <div className="space-y-2">
                  <Label>Author</Label>
                  <Input placeholder="Author" {...regBook("author")} />
                </div>
                <div className="space-y-2">
                  <Label>ISBN</Label>
                  <Input placeholder="978-…" {...regBook("isbn")} />
                </div>
                <div className="space-y-2">
                  <Label>Category</Label>
                  <Input placeholder="Science" {...regBook("category")} />
                </div>
                <div className="space-y-2">
                  <Label>Publisher</Label>
                  <Input placeholder="Publisher" {...regBook("publisher")} />
                </div>
                <div className="space-y-2">
                  <Label>Year</Label>
                  <Input type="number" placeholder="2024" {...regBook("year")} />
                </div>
                <div className="space-y-2">
                  <Label>Copies</Label>
                  <Input type="number" min="1" placeholder="2" {...regBook("total_copies")} />
                </div>
                <div className="flex items-end gap-2">
                  <Button type="submit" disabled={bookSubmitting}>
                    {bookSubmitting ? "Saving…" : editingBook ? "Update" : "Create"}
                  </Button>
                  {editingBook && <Button type="button" variant="ghost" onClick={() => { setEditingBook(null); resetBook(); setShowBookForm(false); }}>Cancel</Button>}
                </div>
              </form>
            </motion.div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Title</th>
                  <th className="pb-2 font-medium">Author</th>
                  <th className="pb-2 font-medium">Category</th>
                  <th className="pb-2 font-medium text-right">Copies</th>
                  <th className="pb-2 font-medium text-right">Available</th>
                  <th className="pb-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loadingBooks ? (
                  <tr><td colSpan={6}><Skeleton className="my-2 h-6 w-full" /></td></tr>
                ) : books.length === 0 ? (
                  <tr><td colSpan={6} className="py-8 text-center text-muted-foreground">
                    No books in the catalogue yet. Add one above.
                  </td></tr>
                ) : (
                  books.map((b) => (
                    <tr key={b.id} className="border-b last:border-0 hover:bg-accent/40">
                      <td className="py-2.5 font-medium">
                        {b.title}
                        {b.isbn && <p className="font-mono text-xs text-muted-foreground">{b.isbn}</p>}
                      </td>
                      <td className="py-2.5">{b.author ?? "—"}</td>
                      <td className="py-2.5">{b.category ?? "—"}</td>
                      <td className="py-2.5 text-right">{b.total_copies}</td>
                      <td className={`py-2.5 text-right font-medium ${b.available_copies === 0 ? "text-destructive" : "text-emerald-600"}`}>
                        {b.available_copies}
                      </td>
                      <td className="py-2.5 text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setEditingBook(b.id);
                            setShowBookForm(true);
                            resetBook({
                              title: b.title,
                              author: b.author ?? "",
                              isbn: b.isbn ?? "",
                              category: b.category ?? "",
                              publisher: b.publisher ?? "",
                              year: b.year ?? undefined,
                              total_copies: b.total_copies,
                            });
                          }}
                        >
                          Edit
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Check out */}
      <Card>
        <CardHeader>
          <CardTitle>Check out</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={submitBorrow((v) => {
              const payload = {
                book_id: v.book_id,
                borrower_type: v.borrower_type,
                student_id: v.borrower_type === "student" ? v.student_id || null : null,
                staff_id: v.borrower_type === "staff" ? v.staff_id || null : null,
                due_on: v.due_on,
              };
              checkOut.mutate(payload, { onSuccess: () => resetBorrow() });
            })}
            className="grid gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-5"
          >
            <div className="space-y-2">
              <Label>Book</Label>
              <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regBorrow("book_id")}>
                <option value="">Choose…</option>
                {books.filter((b) => b.available_copies > 0).map((b) => (
                  <option key={b.id} value={b.id}>{b.title} ({b.available_copies} avail)</option>
                ))}
              </select>
              {borrowErrors.book_id && <p className="text-xs text-destructive">{borrowErrors.book_id.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Borrower type</Label>
              <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regBorrow("borrower_type")}>
                <option value="student">Student</option>
                <option value="staff">Staff</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label>Student</Label>
              <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regBorrow("student_id")}>
                <option value="">Choose…</option>
                {students.map((s) => <option key={s.id} value={s.id}>{s.admission_no} · {s.full_name}</option>)}
              </select>
            </div>
            <div className="space-y-2">
              <Label>Staff</Label>
              <select className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm" {...regBorrow("staff_id")}>
                <option value="">Choose…</option>
                {staff.map((s) => <option key={s.id} value={s.id}>{s.full_name}</option>)}
              </select>
            </div>
            <div className="flex items-end gap-2">
              <div className="flex-1 space-y-2">
                <Label>Due date</Label>
                <Input type="date" defaultValue={inDays(14)} {...regBorrow("due_on")} />
                {borrowErrors.due_on && <p className="text-xs text-destructive">{borrowErrors.due_on.message}</p>}
              </div>
              <Button type="submit" disabled={borrowSubmitting || checkOut.isPending}>
                {borrowSubmitting ? "Checking out…" : "Check out"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Borrowings */}
      <Card>
        <CardHeader>
          <CardTitle>Borrowings</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="pb-2 font-medium">Book</th>
                  <th className="pb-2 font-medium">Borrower</th>
                  <th className="pb-2 font-medium">Borrowed</th>
                  <th className="pb-2 font-medium">Due</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium text-right">Return</th>
                </tr>
              </thead>
              <tbody>
                {borrowings.length === 0 ? (
                  <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">
                    No borrowings yet.
                  </td></tr>
                ) : (
                  borrowings.map((br) => {
                    const isOverdue = br.status === "borrowed" && br.due_on < todayISO();
                    return (
                      <tr key={br.id} className="border-b last:border-0 hover:bg-accent/40">
                        <td className="py-2.5 font-medium">{br.book_title ?? br.book_id}</td>
                        <td className="py-2.5 capitalize">{br.borrower_name ?? br.borrower_type}</td>
                        <td className="py-2.5">{br.borrowed_on}</td>
                        <td className={`py-2.5 ${isOverdue ? "font-semibold text-destructive" : ""}`}>
                          {br.due_on}
                          {isOverdue && <span className="ml-1 rounded-full bg-rose-500/15 px-2 py-0.5 text-xs text-rose-600">overdue</span>}
                        </td>
                        <td className="py-2.5">
                          <span className={`rounded-full px-2 py-0.5 text-xs capitalize ${br.status === "returned" ? "bg-muted text-muted-foreground" : "bg-emerald-500/15 text-emerald-600"}`}>
                            {br.status}
                          </span>
                        </td>
                        <td className="py-2.5 text-right">
                          {br.status === "borrowed" && (
                            <Button variant="outline" size="sm" onClick={() => returnBk.mutate(br.id)} disabled={returnBk.isPending}>
                              Return
                            </Button>
                          )}
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
    </div>
  );
}