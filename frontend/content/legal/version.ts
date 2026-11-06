/**
 * The version of the terms of service in force.
 *
 * Must equal `CURRENT_TERMS_VERSION` in `app/src/identity/domain/terms.py`:
 * `app` decides who has accepted what, this file says which text they read.
 * A test in `app` reads this line and fails when the two drift apart.
 * Bump both when the terms change in substance — every promoter is asked again.
 */
export const TERMS_VERSION = "2026-11-06"

/** The same date, as the documents print it. */
export const TERMS_DATE = "6 listopada 2026"
