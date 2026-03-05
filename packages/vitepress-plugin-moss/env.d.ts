declare module '*.png' {
  const value: string
  export default value
}

declare module 'virtual:moss-config' {
  const getMossConfig: () => any
  export default getMossConfig
}
