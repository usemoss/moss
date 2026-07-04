import { useEffect } from "react";

const faviconHref = "/Moss-logo.jpeg";

const Favicon: React.FC = () => {
    useEffect(() => {
        const existingLink = document.querySelector<HTMLLinkElement>("link[rel='icon']");
        const link = existingLink ?? document.createElement("link");
        const previousHref = existingLink?.href ?? "";

        link.rel = "icon";
        link.type = "image/jpeg";
        link.href = faviconHref;

        if (!existingLink) {
            document.head.appendChild(link);
        }

        return () => {
            if (previousHref) {
                link.href = previousHref;
            } else if (!existingLink && link.parentElement) {
                link.parentElement.removeChild(link);
            }
        };
    }, []);

    return null;
};

export default Favicon;
