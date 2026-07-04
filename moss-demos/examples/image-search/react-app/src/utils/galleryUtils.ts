import { QueryResultDocumentInfo } from "./searchUtils";

export interface GalleryItem {
  readonly id: string;
  readonly caption: string;
  readonly url: string;
  readonly imageId: string;
}

export const mapRecordToGalleryItem = (record: QueryResultDocumentInfo): GalleryItem | null => {
  const metadata = (record.metadata || {}) as Record<string, string>;
  const imageId = typeof metadata.image_id === "string" ? metadata.image_id : undefined;
  const url = typeof metadata.url === "string" ? metadata.url : undefined;

  if (!imageId || !url) {
    return null;
  }

  return {
    id: record.id,
    caption: record.text,
    url,
    imageId,
  };
};
