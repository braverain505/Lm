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
