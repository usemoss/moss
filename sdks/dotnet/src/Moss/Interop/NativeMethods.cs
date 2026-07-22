using System;
using System.Runtime.InteropServices;

namespace Moss.Interop;

/// <summary>
/// Raw P/Invoke declarations for the native <c>libmoss</c> runtime. Every
/// pointer is passed as <see cref="IntPtr"/> so marshaling stays explicit and
/// identical across platforms. The library name "moss" resolves to
/// <c>libmoss.so</c> (Linux), <c>libmoss.dylib</c> (macOS), or <c>moss.dll</c>
/// (Windows) via the standard .NET native-library search.
/// </summary>
internal static class NativeMethods
{
    private const string Lib = "moss";

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_new(IntPtr projectId, IntPtr projectKey, out IntPtr client);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_client_free(IntPtr client);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_create_index(
        IntPtr client, IntPtr name, IntPtr docs, nuint count, IntPtr modelId, out IntPtr outResult);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_add_docs(
        IntPtr client, IntPtr name, IntPtr docs, nuint count, IntPtr options, out IntPtr outResult);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_delete_docs(
        IntPtr client, IntPtr name, IntPtr ids, nuint count, out IntPtr outResult);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_get_docs(
        IntPtr client, IntPtr name, IntPtr ids, nuint count, out IntPtr outDocs, out nuint outCount);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_get_index(IntPtr client, IntPtr name, out IntPtr outInfo);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_list_indexes(IntPtr client, out IntPtr outInfos, out nuint outCount);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_delete_index(
        IntPtr client, IntPtr name, [MarshalAs(UnmanagedType.I1)] out bool deleted);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_get_job_status(IntPtr client, IntPtr jobId, out IntPtr outResult);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_load_index(
        IntPtr client, IntPtr name, IntPtr options, out IntPtr outInfo);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_unload_index(IntPtr client, IntPtr name);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_refresh_index(IntPtr client, IntPtr name, out IntPtr outResult);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern MossResult moss_client_query(
        IntPtr client, IntPtr name, IntPtr query, IntPtr options, out IntPtr outResult);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern IntPtr moss_last_error();

    // Deallocators for every heap object handed back across the boundary.
    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_free_documents(IntPtr docs, nuint count);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_free_index_info(IntPtr info);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_free_index_info_list(IntPtr infos, nuint count);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_free_job_status_response(IntPtr response);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_free_mutation_result(IntPtr result);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_free_refresh_result(IntPtr result);

    [DllImport(Lib, CallingConvention = CallingConvention.Cdecl)]
    public static extern void moss_free_search_result(IntPtr result);
}
