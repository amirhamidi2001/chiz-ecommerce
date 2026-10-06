// Save in-memory data as a file download, without navigating away.
// Used for authenticated downloads (e.g. PDF invoices) that can't be a plain
// <a href> because the Authorization header must be attached by axios.
export const saveBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoke after the browser has had a chance to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
