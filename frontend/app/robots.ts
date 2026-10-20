import type { MetadataRoute } from "next";

/** The landing and attack pages are public; console pages need a session and stay out of search. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: ["/", "/attack"],
      disallow: [
        "/login",
        "/signup",
        "/dashboard",
        "/cases",
        "/case",
        "/team",
        "/live",
        "/network",
        "/bank",
        "/reports",
        "/audit",
        "/insights",
        "/backend/",
      ],
    },
  };
}
