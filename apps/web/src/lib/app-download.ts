/**
 * The Clearis mobile app.
 *
 * The built Android package ships from `apps/web/public/`, so the site serves it
 * itself and the download button is a plain link rather than a store redirect.
 * Replacing the app means replacing the file — no code change, and every
 * surface (header, hero, final call to action, footer) moves together because
 * they all read the path from here.
 */
export const APP_DOWNLOAD_URL = "/clearis.apk";

/** Suggested filename for the save dialog. */
export const APP_DOWNLOAD_NAME = "clearis.apk";
