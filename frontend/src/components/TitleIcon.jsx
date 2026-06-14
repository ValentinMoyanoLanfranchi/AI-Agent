/**
 * TitleIcon — renderiza un SVG monocromo recoloreado vía CSS mask.
 *
 * Los íconos importados (src/assets/icons) tienen fill negro, invisible sobre el
 * tema oscuro. La técnica de mask permite pintarlos con el color de acento de cada
 * página manteniendo la silueta del SVG original.
 */
export default function TitleIcon({ src, color = 'currentColor', size = 28 }) {
  return (
    <span
      aria-hidden="true"
      style={{
        display: 'inline-block',
        width: size,
        height: size,
        flexShrink: 0,
        verticalAlign: 'middle',
        backgroundColor: color,
        WebkitMaskImage: `url(${src})`,
        maskImage: `url(${src})`,
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
      }}
    />
  )
}
