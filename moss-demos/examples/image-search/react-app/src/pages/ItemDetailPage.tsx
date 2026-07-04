import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { QueryResultDocumentInfo } from "../utils/searchUtils";
import { GalleryItem, mapRecordToGalleryItem } from "../utils/galleryUtils";
import "../styles/ItemDetailPage.css";

const ImageDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const location = useLocation();
  const locationState = location.state as { item?: QueryResultDocumentInfo | GalleryItem } | undefined;
  const initialItem = useMemo(() => {
    const candidate = locationState?.item;
    if (!candidate) return null;

    if ("text" in candidate && "metadata" in candidate) {
      return mapRecordToGalleryItem(candidate as QueryResultDocumentInfo);
    }

    return candidate as GalleryItem;
  }, [locationState]);

  const [isImageAvailable, setIsImageAvailable] = useState(true);
  const galleryItem = initialItem;
  const error = galleryItem
    ? null
    : id
      ? "Open this image from the search results to view details."
      : null;

  useEffect(() => {
    setIsImageAvailable(true);
  }, [galleryItem?.url]);

  const captions = galleryItem?.caption.split(" | ") ?? [];

  return (
    <div className="item-detail-page image-detail-page">
      <Link to="/" className="back-link">
        &larr; Back to search
      </Link>

      <div className="image-detail">
        {error && <p className="image-status">{error}</p>}
        {!error && !galleryItem && (
          <p className="image-status">Select an image from the gallery to view details.</p>
        )}
        {!error && galleryItem && (
          <>
            {isImageAvailable ? (
              <img
                src={galleryItem.url}
                alt={captions[0] ?? galleryItem.caption}
                className="image-detail-asset"
                onError={() => setIsImageAvailable(false)}
              />
            ) : (
              <p className="image-status">We couldn&apos;t load this image right now.</p>
            )}
            {captions.length > 0 && (
              <p className="image-caption-text">
                {captions.join(" \u2022 ")}
              </p>
            )}
            <div className="image-detail-meta">
              <p className="image-id-label">ID: {galleryItem.imageId}</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default ImageDetailPage;
