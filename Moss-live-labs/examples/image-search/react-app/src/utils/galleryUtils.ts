import { QueryResultDocumentInfo, API_PREFIX } from "./searchUtils";

export interface GalleryItem {
  readonly id: string;
  readonly caption: string;
  readonly url: string;
  readonly imageId: string;
}

function photoUrl(imageId: string): string {
  return `${API_PREFIX}/photos/${imageId}`;
}

export const mapRecordToGalleryItem = (record: QueryResultDocumentInfo): GalleryItem | null => {
  const metadata = (record.metadata || {}) as Record<string, string>;
  const imageId = typeof metadata.image_id === "string" ? metadata.image_id : undefined;

  if (!imageId) {
    return null;
  }

  return {
    id: record.id,
    caption: record.text,
    url: photoUrl(imageId),
    imageId,
  };
};
