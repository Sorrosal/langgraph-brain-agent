/** Ids under `landing:whatItDoes.*`; the copy lives in the locale files. */
export const USE_CASES = ['email', 'crm', 'tasks'] as const;

/** Mirrors `rules/default.yaml`. */
export const NEEDS_APPROVAL = ['externalEmail', 'bulkEmail', 'bigDeal', 'deleteTask'] as const;

export const BLOCKED = ['deleteCrm'] as const;
