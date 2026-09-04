/** The engines Datalyst can connect to.
 *
 *  Shared because three screens need it: setup picks from it, and the sidebar
 *  and schema map name the engine you ended up connected to.
 */
export const DATABASES = [
  {
    id: 'postgresql',
    name: 'PostgreSQL',
    hint: 'Relational — tables, columns, foreign keys',
    port: '5432',
  },
  {
    id: 'mongodb',
    name: 'MongoDB',
    hint: 'Document — collections and fields',
    port: '27017',
  },
] as const

export function engineName(id: string): string {
  return DATABASES.find((database) => database.id === id)?.name ?? id
}
