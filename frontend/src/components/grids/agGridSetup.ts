/**
 * AG Grid v32 module registration.
 * Must be imported ONCE before any AgGridReact usage.
 */
import {
  ModuleRegistry,
  ClientSideRowModelModule,
  CsvExportModule,
} from 'ag-grid-community'

ModuleRegistry.registerModules([
  ClientSideRowModelModule,
  CsvExportModule,
])
