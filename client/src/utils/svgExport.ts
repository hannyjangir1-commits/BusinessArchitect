/** Serialize an actual diagram with its resolved styles for a standalone SVG file. */
export function downloadSvg(element: SVGSVGElement, filename: string) {
  const copy = element.cloneNode(true) as SVGSVGElement;
  const originalNodes = [element, ...element.querySelectorAll('*')];
  const copiedNodes = [copy, ...copy.querySelectorAll('*')];
  const properties = ['fill', 'stroke', 'color', 'font-family', 'font-size', 'font-weight', 'opacity'];
  originalNodes.forEach((node, index) => {
    const style = window.getComputedStyle(node);
    const target = copiedNodes[index] as SVGElement;
    for (const property of properties) {
      const value = style.getPropertyValue(property);
      if (value) target.style.setProperty(property, value);
    }
    for (const attribute of Array.from(target.attributes)) {
      if (attribute.value.includes('var(')) {
        const resolved = style.getPropertyValue(attribute.name);
        if (resolved) target.setAttribute(attribute.name, resolved);
      }
    }
  });
  const rawName = (filename || '').replace(/[\r\n\x00-\x1f\x7f/\\]/g, '').trim();
  const safeBase = rawName.replace(/\.svg$/i, '').replace(/[^a-zA-Z0-9_\-\u00A0-\uFFFF]/g, '_').replace(/_+/g, '_').slice(0, 100);
  const cleanFilename = `${safeBase || 'diagram'}.svg`;

  copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
  const blob = new Blob([new XMLSerializer().serializeToString(copy)], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = cleanFilename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Leave the URL alive until the browser has consumed the download.
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
