CREATE TABLE research.inflation_target_rate (
	country nvarchar(64),
	date_publish DATE,
	date_reference DATE,
	[target] float,
	tolerance float,
	realized float,
	obs nvarchar(64),
);