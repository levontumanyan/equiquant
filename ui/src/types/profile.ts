export interface Profile {
	name: string;
	weights: { [key: string]: number; };
	ranges: { [key: string]: { min: number; max: number }; };
	formulas: { [key: string]: string; };
}
