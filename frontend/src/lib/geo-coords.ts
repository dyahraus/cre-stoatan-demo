export interface RegionCoord {
  lat: number;
  lng: number;
  displayName: string;
}

export const REGION_COORDS: Record<string, RegionCoord> = {
  // Macro regions
  US_Southeast: { lat: 33.749, lng: -84.388, displayName: "US Southeast" },
  US_Midwest: { lat: 41.878, lng: -87.630, displayName: "US Midwest" },
  US_Northeast: { lat: 40.713, lng: -74.006, displayName: "US Northeast" },
  US_Southwest: { lat: 33.448, lng: -112.074, displayName: "US Southwest" },
  US_West: { lat: 37.775, lng: -122.419, displayName: "US West" },
  Midwest: { lat: 41.878, lng: -87.630, displayName: "Midwest" },
  Southeast: { lat: 33.749, lng: -84.388, displayName: "Southeast" },
  Northeast: { lat: 40.713, lng: -74.006, displayName: "Northeast" },
  Southwest: { lat: 33.448, lng: -112.074, displayName: "Southwest" },
  West_Coast: { lat: 37.775, lng: -122.419, displayName: "West Coast" },
  Gulf_Coast: { lat: 29.760, lng: -95.370, displayName: "Gulf Coast" },
  Sun_Belt: { lat: 33.448, lng: -112.074, displayName: "Sun Belt" },

  // Major CRE warehouse / logistics metros
  Inland_Empire: { lat: 34.0, lng: -117.4, displayName: "Inland Empire" },
  Dallas_Fort_Worth: { lat: 32.777, lng: -96.797, displayName: "Dallas-Fort Worth" },
  Indianapolis: { lat: 39.768, lng: -86.158, displayName: "Indianapolis" },
  Chicago: { lat: 41.878, lng: -87.630, displayName: "Chicago" },
  Atlanta: { lat: 33.749, lng: -84.388, displayName: "Atlanta" },
  Memphis: { lat: 35.150, lng: -90.049, displayName: "Memphis" },
  Louisville: { lat: 38.253, lng: -85.759, displayName: "Louisville" },
  Columbus: { lat: 39.961, lng: -82.999, displayName: "Columbus, OH" },
  Columbus_OH: { lat: 39.961, lng: -82.999, displayName: "Columbus, OH" },
  Phoenix: { lat: 33.448, lng: -112.074, displayName: "Phoenix" },
  Houston: { lat: 29.760, lng: -95.370, displayName: "Houston" },
  Nashville: { lat: 36.163, lng: -86.781, displayName: "Nashville" },
  Savannah: { lat: 32.081, lng: -81.091, displayName: "Savannah" },
  Kansas_City: { lat: 39.100, lng: -94.579, displayName: "Kansas City" },
  Cincinnati: { lat: 39.162, lng: -84.457, displayName: "Cincinnati" },
  St_Louis: { lat: 38.627, lng: -90.199, displayName: "St. Louis" },
  Minneapolis: { lat: 44.978, lng: -93.265, displayName: "Minneapolis" },
  Milwaukee: { lat: 43.039, lng: -87.907, displayName: "Milwaukee" },
  Detroit: { lat: 42.331, lng: -83.046, displayName: "Detroit" },
  Denver: { lat: 39.739, lng: -104.990, displayName: "Denver" },
  Las_Vegas: { lat: 36.169, lng: -115.140, displayName: "Las Vegas" },
  Salt_Lake_City: { lat: 40.761, lng: -111.891, displayName: "Salt Lake City" },
  Reno: { lat: 39.530, lng: -119.814, displayName: "Reno" },
  Seattle: { lat: 47.606, lng: -122.332, displayName: "Seattle" },
  Portland: { lat: 45.505, lng: -122.675, displayName: "Portland" },
  Los_Angeles: { lat: 34.052, lng: -118.244, displayName: "Los Angeles" },
  San_Francisco: { lat: 37.775, lng: -122.419, displayName: "San Francisco" },
  New_Jersey: { lat: 40.058, lng: -74.406, displayName: "New Jersey" },
  Lehigh_Valley: { lat: 40.602, lng: -75.470, displayName: "Lehigh Valley" },
  Central_PA: { lat: 40.269, lng: -76.876, displayName: "Central PA" },
  Charlotte: { lat: 35.227, lng: -80.843, displayName: "Charlotte" },
  Greenville_Spartanburg: { lat: 34.852, lng: -82.394, displayName: "Greenville-Spartanburg" },
  Jacksonville: { lat: 30.332, lng: -81.656, displayName: "Jacksonville" },
  Tampa: { lat: 27.951, lng: -82.458, displayName: "Tampa" },
  Miami: { lat: 25.762, lng: -80.192, displayName: "Miami" },
  San_Antonio: { lat: 29.425, lng: -98.495, displayName: "San Antonio" },
  Austin: { lat: 30.267, lng: -97.743, displayName: "Austin" },
  El_Paso: { lat: 31.762, lng: -106.445, displayName: "El Paso" },
  Oklahoma_City: { lat: 35.468, lng: -97.517, displayName: "Oklahoma City" },
  Tulsa: { lat: 36.154, lng: -95.993, displayName: "Tulsa" },
  Allentown: { lat: 40.602, lng: -75.470, displayName: "Allentown" },
  Baltimore: { lat: 39.290, lng: -76.612, displayName: "Baltimore" },
  Richmond: { lat: 37.541, lng: -77.436, displayName: "Richmond" },
  Norfolk: { lat: 36.851, lng: -76.286, displayName: "Norfolk" },
  Trenton: { lat: 40.217, lng: -74.743, displayName: "Trenton" },
  Boston: { lat: 42.360, lng: -71.059, displayName: "Boston" },
  New_York: { lat: 40.713, lng: -74.006, displayName: "New York" },
  Pennsylvania: { lat: 40.269, lng: -76.876, displayName: "Pennsylvania" },
  Texas: { lat: 31.969, lng: -99.902, displayName: "Texas" },
  California: { lat: 36.778, lng: -119.418, displayName: "California" },
  Florida: { lat: 27.665, lng: -81.516, displayName: "Florida" },
  Georgia: { lat: 32.165, lng: -82.900, displayName: "Georgia" },
  Ohio: { lat: 40.418, lng: -82.907, displayName: "Ohio" },
  Tennessee: { lat: 35.517, lng: -86.581, displayName: "Tennessee" },
};

export function getRegionCoord(region: string): RegionCoord | null {
  return REGION_COORDS[region] ?? null;
}

export function formatRegionName(region: string): string {
  return REGION_COORDS[region]?.displayName ?? region.replace(/_/g, " ");
}
