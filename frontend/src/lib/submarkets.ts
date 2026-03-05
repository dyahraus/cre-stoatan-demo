export interface Submarket {
  id: string;
  name: string;
  lat: number;
  lng: number;
  score: number;
  trend: "up" | "stable" | "down";
  sector: string;
  vacancy: number;
}

export const MIDWEST_SUBMARKETS: Submarket[] = [
  { id: "chi_cbd", name: "Chicago CBD", lat: 41.8781, lng: -87.6298, score: 87, trend: "up", sector: "Industrial", vacancy: 4.2 },
  { id: "chi_ohare", name: "O'Hare Corridor", lat: 41.9742, lng: -87.9073, score: 92, trend: "up", sector: "Logistics", vacancy: 3.1 },
  { id: "chi_south", name: "South Suburbs", lat: 41.525, lng: -87.69, score: 71, trend: "stable", sector: "Distribution", vacancy: 5.8 },
  { id: "chi_i80", name: "I-80 Corridor", lat: 41.506, lng: -88.15, score: 95, trend: "up", sector: "Warehouse", vacancy: 2.4 },
  { id: "indy_west", name: "Indianapolis West", lat: 39.7684, lng: -86.358, score: 78, trend: "up", sector: "Distribution", vacancy: 4.9 },
  { id: "indy_east", name: "Indianapolis East", lat: 39.78, lng: -85.95, score: 65, trend: "stable", sector: "Industrial", vacancy: 6.2 },
  { id: "columbus", name: "Columbus Central", lat: 39.9612, lng: -82.9988, score: 83, trend: "up", sector: "E-Commerce", vacancy: 3.7 },
  { id: "detroit_metro", name: "Detroit Metro", lat: 42.3314, lng: -83.0458, score: 59, trend: "down", sector: "Automotive", vacancy: 7.8 },
  { id: "milwaukee", name: "Milwaukee Industrial", lat: 43.0389, lng: -87.9065, score: 74, trend: "stable", sector: "Manufacturing", vacancy: 5.1 },
  { id: "stl_east", name: "St. Louis East", lat: 38.627, lng: -90.1994, score: 68, trend: "stable", sector: "Distribution", vacancy: 6.0 },
  { id: "minneapolis", name: "Minneapolis Corridor", lat: 44.9778, lng: -93.265, score: 81, trend: "up", sector: "Logistics", vacancy: 4.0 },
  { id: "kc_industrial", name: "Kansas City Industrial", lat: 39.0997, lng: -94.5786, score: 76, trend: "up", sector: "Intermodal", vacancy: 4.5 },
  { id: "cin_north", name: "Cincinnati North", lat: 39.162, lng: -84.4569, score: 72, trend: "stable", sector: "Industrial", vacancy: 5.4 },
  { id: "grandrapids", name: "Grand Rapids", lat: 42.9634, lng: -85.6681, score: 63, trend: "down", sector: "Manufacturing", vacancy: 6.8 },
];

export interface DrilldownRegion {
  submarkets: Submarket[];
  center: { lat: number; lng: number };
  zoomDistance: number;
}

export const DRILLDOWN_REGIONS: Record<string, DrilldownRegion> = {
  US_Midwest: { submarkets: MIDWEST_SUBMARKETS, center: { lat: 41.0, lng: -87.5 }, zoomDistance: 1.65 },
  Midwest: { submarkets: MIDWEST_SUBMARKETS, center: { lat: 41.0, lng: -87.5 }, zoomDistance: 1.65 },
};
