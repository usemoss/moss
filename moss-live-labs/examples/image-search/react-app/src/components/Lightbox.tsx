import { useCallback, useEffect } from "react";
import { GalleryItem } from "../utils/galleryUtils";
import "../styles/Lightbox.css";

interface LightboxProps {
  readonly item: GalleryItem;
  readonly items: readonly GalleryItem[];
  readonly onClose: () => void;
  readonly onNavigate: (item: GalleryItem) => void;
  readonly onFindSimilar: (caption: string) => void;
}

const Lightbox = ({ item, items, onClose, onNavigate, onFindSimilar }: LightboxProps) => {
  const captions = item.caption.split(" | ");
  const firstCaption = captions[0] ?? item.caption;
  const currentIndex = items.findIndex((i) => i.id === item.id);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < items.length - 1;

  const goToPrev = useCallback(() => {
    if (hasPrev) onNavigate(items[currentIndex - 1]);
  }, [hasPrev, items, currentIndex, onNavigate]);

  const goToNext = useCallback(() => {
    if (hasNext) onNavigate(items[currentIndex + 1]);
  }, [hasNext, items, currentIndex, onNavigate]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") goToPrev();
      if (e.key === "ArrowRight") goToNext();
    },
    [onClose, goToPrev, goToNext],
  );

  useEffect(() => {
    document.addEventListener("keydown", handleKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [handleKeyDown]);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  const handleFindSimilar = () => {
    onFindSimilar(firstCaption);
  };

  return (
    <div className="lightbox-backdrop" onClick={handleBackdropClick}>
      <div className="lightbox-content">
        <button type="button" className="lightbox-close" onClick={onClose} aria-label="Close">
          &#x2715;
        </button>
        <div className="lightbox-image-container">
          <img src={item.url} alt={firstCaption} className="lightbox-image" />
          {hasPrev && (
            <button type="button" className="lightbox-nav lightbox-nav--prev" onClick={goToPrev} aria-label="Previous">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" stroke="#fff" />
              </svg>
            </button>
          )}
          {hasNext && (
            <button type="button" className="lightbox-nav lightbox-nav--next" onClick={goToNext} aria-label="Next">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 6 15 12 9 18" stroke="#fff" />
              </svg>
            </button>
          )}
        </div>
        <div className="lightbox-info">
          <div className="lightbox-captions">
            {captions.map((cap, i) => (
              <p key={`${item.id}-${i}`} className="lightbox-caption">{cap.trim()}</p>
            ))}
          </div>
          <p className="lightbox-id">ID: {item.imageId}</p>
          <button type="button" className="lightbox-find-similar" onClick={handleFindSimilar}>
            Find similar
          </button>
        </div>
      </div>
    </div>
  );
};

export default Lightbox;
