// Idempotent hotel seed for the frontend dropdown.
// Run: docker compose exec -T mongodb mongosh -u admin -p admin123 \
//        --authenticationDatabase admin hotel --quiet --file /dev/stdin < scripts/seed_hotels.js
const sample = [
  { name: "Sunset Resort", description: "Beachfront resort with sunset views", location: "Eilat", price_per_night: 520 },
  { name: "Ocean View Hotel", description: "Modern rooms overlooking the sea", location: "Tel Aviv", price_per_night: 610 },
  { name: "Mountain Retreat", description: "Quiet getaway in the hills", location: "Safed", price_per_night: 380 },
  { name: "City Lights Inn", description: "Boutique hotel in the city center", location: "Jerusalem", price_per_night: 450 },
];

for (const hotel of sample) {
  const exists = db.hotels.findOne({ name: hotel.name });
  if (!exists) {
    db.hotels.insertOne(hotel);
    print("inserted: " + hotel.name);
  } else {
    print("exists:   " + hotel.name);
  }
}
print("total hotels: " + db.hotels.countDocuments());
