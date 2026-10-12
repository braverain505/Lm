/**
 * Client-side CSV download, used for handing out result codes and other
 * tabular exports. Values are escaped per RFC 4180 and the file carries a UTF-8
 * BOM so Excel opens it with the right encoding.
 */
export function downloadCsv(
  filename: string,
  rows: (string | number | null | undefined)[][],
): void {
  const escape = (value: string | number | null | undefined): string => {
    const text = value == null ? "" : String(value);
    return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };

  const csv = rows.map((row) => row.map(escape).join(",")).join("\r\n");
  const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Make a label safe to sit inside a download filename.
 *
 * Class, subject and term names come from the school — "JSS 2B", "Basic
 * Science", "First Term" — and may contain spaces, slashes or punctuation that
 * browsers turn into underscores or, worse, truncate at. "JSS 2B · First Term"
 * becomes "jss-2b-first-term".
 */
export function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48) || "export";
}
