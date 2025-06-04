const express = require('express');
const cors = require('cors');
const app = express();
const PORT = 5000;

app.use(cors());
app.use(express.json());

app.get('/api/jobs', (req, res) => {
    const { lat, lng, radius } = req.query;

    const jobs = [
        {
            id: "1",
            title: "Frontend Developer",
            company: "Tech Corp",
            location: "New York, NY",
            salary: "$80,000 - $100,000",
            type: "Full-time",
            description: "Build UI with React.",
            requirements: ["React", "Tailwind", "JavaScript"],
            skills: ["React", "Tailwind"],
            source: "naukri",
            posted: "1 day ago",
            url: "https://example.com/job1"
        },
        {
            id: "2",
            title: "Backend Developer",
            company: "DevCo",
            location: "Brooklyn, NY",
            salary: "$90,000 - $110,000",
            type: "Full-time",
            description: "Node.js API development.",
            requirements: ["Node.js", "Express", "MongoDB"],
            skills: ["Node.js", "MongoDB"],
            source: "linkedin",
            posted: "2 days ago",
            url: "https://example.com/job2"
        }
    ];

    res.json(jobs);
});

app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});