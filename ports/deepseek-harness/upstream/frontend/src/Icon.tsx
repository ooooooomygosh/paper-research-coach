import book from './icons/book.svg?raw';
import layers from './icons/layers.svg?raw';
import explain from './icons/explain.svg?raw';
import translate from './icons/translate.svg?raw';
import original from './icons/original.svg?raw';
import download from './icons/download.svg?raw';
import close from './icons/close.svg?raw';
import locate from './icons/locate.svg?raw';

const icons = { book, layers, explain, translate, original, download, close, locate };
/** Only bundled, independently stored SVG resources enter this component. */
export default function Icon({ name }: { name: keyof typeof icons }) {
  return <span className="prc-icon" aria-hidden="true" dangerouslySetInnerHTML={{ __html: icons[name] }} />;
}
