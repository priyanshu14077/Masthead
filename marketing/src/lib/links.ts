// The landing page and the app are served by the same Masthead server: the page at "/", the app at "/app/".
// `app("#/settings/billing")` deep-links into a screen of the app.
export const APP_HOME = "/app/"
export const app = (screen = "") => APP_HOME + screen
// TODO: a real address for demo requests.
export const DEMO_URL = "mailto:hello@masthead.example"
